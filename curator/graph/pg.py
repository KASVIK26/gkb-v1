"""Create KG release schemas in PostgreSQL and load bundles into them."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from curator.graph.bundle import KGBundle
from curator.model.enums import EVIDENCE_WEIGHT

DB_DIR = Path(__file__).resolve().parents[2] / "db"
_SCHEMA_RE = re.compile(r"^kg_[a-z0-9_]{1,50}$")


class GateError(RuntimeError):
    """The bundle failed its release gates and must not be loaded."""


def _check_schema(schema: str) -> str:
    if not _SCHEMA_RE.match(schema):
        raise ValueError(f"release schema must match {_SCHEMA_RE.pattern}: {schema!r}")
    return schema


def set_search_path(conn: psycopg.Connection, schema: str) -> None:
    conn.execute(f"SET search_path = {_check_schema(schema)}, extensions, public")


def create_release_schema(conn: psycopg.Connection, schema: str, *, postgis: bool = False) -> None:
    """Create an empty release schema (fails if it already exists: releases are immutable)."""
    conn.execute(f"CREATE SCHEMA {_check_schema(schema)}")
    set_search_path(conn, schema)
    conn.execute((DB_DIR / "release_schema.sql").read_text(encoding="utf-8"))
    if postgis:
        conn.execute((DB_DIR / "release_schema_postgis.sql").read_text(encoding="utf-8"))


def load_bundle(
    conn: psycopg.Connection, schema: str, bundle: KGBundle, *, allow_test_sources: bool = False
) -> dict[str, int]:
    errors = bundle.gate_errors(allow_test_sources=allow_test_sources)
    if errors:
        raise GateError(f"{len(errors)} release gate error(s):\n" + "\n".join(errors[:50]))

    set_search_path(conn, schema)
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO source (id, type, title, year, venue, url, license, verified)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            [(s.id, s.type.value, s.title, s.year, s.venue, s.url, s.license, s.verified) for s in bundle.sources],
        )
        cur.executemany(
            "INSERT INTO entity (id, type, crop, name, name_i18n, props) VALUES (%s, %s, %s, %s, %s, %s)",
            [
                (e.id, e.type.value, e.crop.value if e.crop else None, e.name, Jsonb(e.name_i18n), Jsonb(e.props))
                for e in bundle.entities
            ],
        )
        cur.executemany(
            "INSERT INTO entity_synonym (entity_id, synonym) VALUES (%s, %s)",
            [(e.id, syn) for e in bundle.entities for syn in dict.fromkeys(e.synonyms)],
        )
        cur.executemany(
            "INSERT INTO claim (id, type, subject_id, object_id, qualifiers, status, score, tier, conflict)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [
                (
                    c.id, c.type.value, c.subject_id, c.object_id, Jsonb(c.qualifiers), c.status.value,
                    c.score, c.tier.value if c.tier else None, c.conflict,
                )
                for c in bundle.claims
            ],
        )
        cur.executemany(
            "INSERT INTO evidence (id, claim_id, source_id, method, extractor, locator, quote,"
            " reviewer, reviewed_at, weight) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [
                (
                    ev.id, ev.claim_id, ev.source_id, ev.method.value, ev.extractor, ev.locator, ev.quote,
                    ev.reviewer, ev.reviewed_at, EVIDENCE_WEIGHT[ev.method],
                )
                for ev in bundle.evidence
            ],
        )
    return {
        "sources": len(bundle.sources),
        "entities": len(bundle.entities),
        "claims": len(bundle.claims),
        "evidence": len(bundle.evidence),
    }


def run_cq(conn: psycopg.Connection, schema: str, name: str, **params: Any) -> list[dict[str, Any]]:
    """Run a competency-question query from db/cq/<name>.sql against a release schema."""
    sql_path = DB_DIR / "cq" / f"{name}.sql"
    set_search_path(conn, schema)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql_path.read_text(encoding="utf-8"), params)
        return cur.fetchall()
