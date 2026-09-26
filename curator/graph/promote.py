"""Atomic switchover: point `kg_current` at a specific, already-loaded release schema.

Design (TECH_STACK.md ADR-7): a release lives in its own immutable schema (`kg_<release>`,
created once by `create_release_schema` + `load_bundle` in pg.py, never touched again). "Which
release is live" is a separate, cheap operation on top of that: `kg_current` is a schema of
plain views, one per table/view found in the release schema, all pointing at that release's
objects. Promoting a new release means dropping and recreating every one of those views inside
a single transaction, so a reader never sees a half-switched state (some views on the old
release, some on the new one) -- Postgres DDL is transactional, so the whole batch commits or
none of it does.

Rolling back is just promoting an older release again; this module never drops a `kg_<release>`
schema itself (that stays a manual, deliberate decision, kept out of automated tooling).

`kg_meta.release_history` is an append-only log -- insert only, never updated -- so "what was
current, and since when" is auditable without extra bookkeeping inside each release schema.
"""

from __future__ import annotations

import psycopg

from curator.graph.pg import _check_schema

KG_META_SCHEMA = "kg_meta"
KG_CURRENT_SCHEMA = "kg_current"


class PromoteError(RuntimeError):
    """The release failed the pre-promotion sanity gate and was not promoted."""


def ensure_meta_schema(conn: psycopg.Connection) -> None:
    conn.execute(f"CREATE SCHEMA IF NOT EXISTS {KG_META_SCHEMA}")
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {KG_META_SCHEMA}.release_history (
            id BIGSERIAL PRIMARY KEY,
            release TEXT NOT NULL,
            switched_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def _relations_in_schema(conn: psycopg.Connection, schema: str) -> list[str]:
    """Names of every table/view directly in `schema` (relkind 'r' table, 'v' view)."""
    rows = conn.execute(
        """
        SELECT c.relname
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = %s AND c.relkind IN ('r', 'v')
        ORDER BY c.relname
        """,
        (schema,),
    ).fetchall()
    return [r[0] for r in rows]


def promote(
    conn: psycopg.Connection, release_schema: str, *, min_entities: int = 1, min_claims: int = 1
) -> dict[str, object]:
    """Atomically point kg_current at `release_schema`.

    Raises PromoteError (without touching kg_current) if the schema doesn't exist, has no
    tables/views, or looks implausibly empty. This is a light sanity gate, not the full QC
    report from Phase 9 -- it exists to stop an obviously wrong schema name or an empty load
    from becoming "current" by accident, nothing more.
    """
    _check_schema(release_schema)

    exists = conn.execute(
        "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s", (release_schema,)
    ).fetchone()
    if not exists:
        raise PromoteError(f"schema {release_schema!r} does not exist -- nothing to promote")

    n_entities = conn.execute(f"SELECT count(*) FROM {release_schema}.entity").fetchone()[0]
    n_claims = conn.execute(f"SELECT count(*) FROM {release_schema}.claim").fetchone()[0]
    if n_entities < min_entities or n_claims < min_claims:
        raise PromoteError(
            f"{release_schema} has {n_entities} entities / {n_claims} claims, below the minimum "
            f"({min_entities}/{min_claims}) -- refusing to promote"
        )

    relations = _relations_in_schema(conn, release_schema)
    if not relations:
        raise PromoteError(f"{release_schema} has no tables or views -- refusing to promote")

    ensure_meta_schema(conn)
    with conn.transaction():
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {KG_CURRENT_SCHEMA}")
        for name in relations:
            # DROP+CREATE (not CREATE OR REPLACE) so this survives a release whose column list
            # changed shape between releases -- CREATE OR REPLACE VIEW forbids that.
            conn.execute(f'DROP VIEW IF EXISTS {KG_CURRENT_SCHEMA}."{name}" CASCADE')
        for name in relations:
            conn.execute(f'CREATE VIEW {KG_CURRENT_SCHEMA}."{name}" AS SELECT * FROM {release_schema}."{name}"')
        conn.execute(f"INSERT INTO {KG_META_SCHEMA}.release_history (release) VALUES (%s)", (release_schema,))

    return {"promoted": release_schema, "entities": n_entities, "claims": n_claims, "relations": len(relations)}


def current_release(conn: psycopg.Connection) -> str | None:
    ensure_meta_schema(conn)
    row = conn.execute(
        f"SELECT release FROM {KG_META_SCHEMA}.release_history ORDER BY switched_at DESC, id DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def release_history(conn: psycopg.Connection) -> list[dict[str, object]]:
    ensure_meta_schema(conn)
    rows = conn.execute(
        f"SELECT release, switched_at FROM {KG_META_SCHEMA}.release_history ORDER BY switched_at DESC, id DESC"
    ).fetchall()
    return [{"release": r[0], "switched_at": r[1]} for r in rows]
