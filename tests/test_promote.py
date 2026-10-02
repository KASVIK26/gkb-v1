"""Atomic kg_current switchover tests against a throwaway PostgreSQL."""

from __future__ import annotations

import uuid

import psycopg
import pytest
from kg_toy import toy_bundle

from curator.graph.pg import create_release_schema, load_bundle
from curator.graph.promote import (
    KG_CURRENT_SCHEMA,
    MIGRATIONS_DIR,
    PromoteError,
    bridge_view_sql,
    current_release,
    promote,
    release_history,
)


@pytest.fixture()
def loaded_schema(pg_conn: psycopg.Connection, release_schema: str) -> str:
    create_release_schema(pg_conn, release_schema)
    load_bundle(pg_conn, release_schema, toy_bundle(), allow_test_sources=True)
    return release_schema


@pytest.fixture(autouse=True)
def _drop_kg_current(pg_conn: psycopg.Connection):
    yield
    pg_conn.execute(f"DROP SCHEMA IF EXISTS {KG_CURRENT_SCHEMA} CASCADE")
    pg_conn.execute("DROP SCHEMA IF EXISTS kg_meta CASCADE")


def test_promote_creates_views_matching_release_counts(pg_conn, loaded_schema):
    result = promote(pg_conn, loaded_schema)
    assert result["promoted"] == loaded_schema
    assert result["entities"] > 0 and result["claims"] > 0

    n_current = pg_conn.execute(f"SELECT count(*) FROM {KG_CURRENT_SCHEMA}.entity").fetchone()[0]
    n_release = pg_conn.execute(f"SELECT count(*) FROM {loaded_schema}.entity").fetchone()[0]
    assert n_current == n_release == result["entities"]


def test_promote_records_history(pg_conn, loaded_schema):
    promote(pg_conn, loaded_schema)
    assert current_release(pg_conn) == loaded_schema
    history = release_history(pg_conn)
    assert history[0]["release"] == loaded_schema
    assert len(history) == 1


def test_promoting_a_second_release_atomically_repoints_every_view(pg_conn, loaded_schema, release_schema):
    promote(pg_conn, loaded_schema)

    second = f"kg_test_{uuid.uuid4().hex[:10]}"
    create_release_schema(pg_conn, second)
    load_bundle(pg_conn, second, toy_bundle(), allow_test_sources=True)
    try:
        promote(pg_conn, second)

        assert current_release(pg_conn) == second
        history = release_history(pg_conn)
        assert [h["release"] for h in history] == [second, loaded_schema]

        # every view in kg_current must now depend on `second`'s tables, none left over on the first
        # release -- pg_get_viewdef can omit the schema qualifier when it matches search_path, so
        # resolve the dependency directly via the catalog instead of parsing view SQL text.
        deps = pg_conn.execute(
            "SELECT DISTINCT table_schema FROM information_schema.view_table_usage"
            " WHERE view_schema = %s",
            (KG_CURRENT_SCHEMA,),
        ).fetchall()
        assert deps, "expected kg_current views to depend on some schema"
        dep_schemas = {row[0] for row in deps}
        assert dep_schemas == {second}
        assert loaded_schema not in dep_schemas
    finally:
        pg_conn.execute(f"DROP SCHEMA IF EXISTS {second} CASCADE")


def test_promote_refuses_nonexistent_schema_without_touching_kg_current(pg_conn):
    with pytest.raises(PromoteError, match="does not exist"):
        promote(pg_conn, "kg_does_not_exist_at_all")
    exists = pg_conn.execute(
        "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s", (KG_CURRENT_SCHEMA,)
    ).fetchone()
    assert exists is None


def test_promote_refuses_implausibly_empty_schema(pg_conn, release_schema):
    create_release_schema(pg_conn, release_schema)  # no data loaded
    with pytest.raises(PromoteError, match="below the minimum"):
        promote(pg_conn, release_schema)


def test_promote_rejects_invalid_schema_name(pg_conn):
    with pytest.raises(ValueError, match="release schema must match"):
        promote(pg_conn, "not-a-valid-schema-name; DROP TABLE x")


def test_current_release_is_none_before_any_promotion(pg_conn):
    assert current_release(pg_conn) is None
    assert release_history(pg_conn) == []


# ───────── dependents of kg_current (the public.kg_* bridge views the dashboard reads) ─────────

def _make_second_release(pg_conn) -> str:
    second = f"kg_test_{uuid.uuid4().hex[:10]}"
    create_release_schema(pg_conn, second)
    load_bundle(pg_conn, second, toy_bundle(), allow_test_sources=True)
    return second


def _view_exists(pg_conn, name: str) -> bool:
    return pg_conn.execute(
        "SELECT 1 FROM information_schema.views WHERE table_schema = 'public' AND table_name = %s", (name,)
    ).fetchone() is not None


def test_promoting_again_drops_views_built_on_kg_current_unless_they_are_reapplied(pg_conn, loaded_schema):
    # The hazard that took the live dashboard down: promote() drops kg_current's views with CASCADE.
    view = f"bridge_{uuid.uuid4().hex[:8]}"
    promote(pg_conn, loaded_schema)
    pg_conn.execute(f"CREATE VIEW public.{view} AS SELECT id FROM kg_current.entity")
    second = _make_second_release(pg_conn)
    try:
        promote(pg_conn, second)
        assert not _view_exists(pg_conn, view)
    finally:
        pg_conn.execute(f"DROP VIEW IF EXISTS public.{view}")
        pg_conn.execute(f"DROP SCHEMA IF EXISTS {second} CASCADE")


def test_bridge_sql_keeps_dependent_views_alive_across_promotions(pg_conn, loaded_schema):
    view = f"bridge_{uuid.uuid4().hex[:8]}"
    bridge = [f"CREATE OR REPLACE VIEW public.{view} AS SELECT id, name FROM kg_current.entity"]
    promote(pg_conn, loaded_schema, bridge_sql=bridge)
    second = _make_second_release(pg_conn)
    try:
        promote(pg_conn, second, bridge_sql=bridge)
        assert _view_exists(pg_conn, view)
        assert pg_conn.execute(f"SELECT count(*) FROM public.{view}").fetchone()[0] > 0
    finally:
        pg_conn.execute(f"DROP VIEW IF EXISTS public.{view}")
        pg_conn.execute(f"DROP SCHEMA IF EXISTS {second} CASCADE")


def test_failing_bridge_sql_rolls_the_whole_promotion_back(pg_conn, loaded_schema):
    with pytest.raises(psycopg.Error):
        promote(pg_conn, loaded_schema, bridge_sql=["CREATE VIEW public.never_created AS SELECT nope FROM kg_current.entity"])
    assert current_release(pg_conn) is None
    assert pg_conn.execute(
        "SELECT 1 FROM information_schema.views WHERE table_schema = %s", (KG_CURRENT_SCHEMA,)
    ).fetchone() is None


def test_bridge_view_sql_picks_up_only_the_views_migrations_in_order():
    files = sorted(p.name for p in MIGRATIONS_DIR.glob("*_views.sql"))
    assert files == sorted(files) and len(files) >= 3
    assert all("staging" not in name for name in files)
    assert len(bridge_view_sql()) == len(files)
