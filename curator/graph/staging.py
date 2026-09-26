"""Read/write staging.pending_source / staging.pending_claim -- the holding area between LLM
extraction and a real release. See supabase/migrations/20260927000000_staging_claims.sql for the
schema and why it deliberately sits outside every kg_<release> schema.

Rows written here are already-validated curator.model.claims.Claim/Evidence/Source objects (they
passed grounding + normalization before reaching this module) -- this module does no validation of
its own beyond what the DB CHECK constraints enforce; it is a plain data-access layer, matching the
conventions in curator/graph/pg.py (Jsonb(...) wrapping, dict_row for reads, psycopg named params).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from curator.model.claims import Claim, Evidence, Source

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "20260927000000_staging_claims.sql"
)


def ensure_staging_schema(conn: psycopg.Connection) -> None:
    """Create the staging schema/tables if they don't exist yet -- idempotent, safe to call every
    time (mirrors the migration file exactly; used by tests against a throwaway Postgres instance
    that never ran the Supabase migrations by hand)."""
    conn.execute("CREATE SCHEMA IF NOT EXISTS staging")
    exists = conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'staging' AND table_name = 'pending_claim'"
    ).fetchone()
    if not exists:
        conn.execute(MIGRATION_PATH.read_text(encoding="utf-8"))


def insert_pending_source(conn: psycopg.Connection, source: Source) -> None:
    """Idempotent: the same paper may be extracted more than once."""
    conn.execute(
        """
        INSERT INTO staging.pending_source (id, type, title, year, venue, url, license, verified)
        VALUES (%(id)s, %(type)s, %(title)s, %(year)s, %(venue)s, %(url)s, %(license)s, %(verified)s)
        ON CONFLICT (id) DO NOTHING
        """,
        {
            "id": source.id,
            "type": source.type.value,
            "title": source.title,
            "year": source.year,
            "venue": source.venue,
            "url": source.url,
            "license": source.license,
            "verified": source.verified,
        },
    )


def insert_pending_claim(
    conn: psycopg.Connection,
    *,
    claim: Claim,
    evidence: Evidence,
    llm_model: str | None,
    grounding_score: float | None,
    source_relevance: dict[str, Any] | None,
) -> int:
    row = conn.execute(
        """
        INSERT INTO staging.pending_claim
            (claim_type, subject_id, object_id, qualifiers, source_id, method, extractor,
             locator, quote, llm_model, grounding_score, source_relevance)
        VALUES (%(claim_type)s, %(subject_id)s, %(object_id)s, %(qualifiers)s, %(source_id)s,
                %(method)s, %(extractor)s, %(locator)s, %(quote)s, %(llm_model)s,
                %(grounding_score)s, %(source_relevance)s)
        RETURNING id
        """,
        {
            "claim_type": claim.type.value,
            "subject_id": claim.subject_id,
            "object_id": claim.object_id,
            "qualifiers": Jsonb(claim.qualifiers),
            "source_id": evidence.source_id,
            "method": evidence.method.value,
            "extractor": evidence.extractor,
            "locator": evidence.locator,
            "quote": evidence.quote,
            "llm_model": llm_model,
            "grounding_score": grounding_score,
            "source_relevance": Jsonb(source_relevance) if source_relevance is not None else None,
        },
    ).fetchone()
    return row[0]


def list_pending(conn: psycopg.Connection, *, status: str = "pending_review") -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT pc.*, ps.title AS source_title, ps.venue AS source_venue, ps.year AS source_year,
                   ps.url AS source_url, ps.verified AS source_verified
            FROM staging.pending_claim pc
            JOIN staging.pending_source ps ON ps.id = pc.source_id
            WHERE pc.status = %(status)s
            ORDER BY pc.created_at DESC
            """,
            {"status": status},
        )
        return cur.fetchall()


def approve_pending(conn: psycopg.Connection, claim_id: int, *, reviewer: str) -> None:
    conn.execute(
        "UPDATE staging.pending_claim SET status = 'approved', reviewer = %(reviewer)s, reviewed_at = now()"
        " WHERE id = %(id)s AND status = 'pending_review'",
        {"reviewer": reviewer, "id": claim_id},
    )


def reject_pending(conn: psycopg.Connection, claim_id: int, *, reviewer: str, reason: str) -> None:
    conn.execute(
        "UPDATE staging.pending_claim SET status = 'rejected', reviewer = %(reviewer)s, reviewed_at = now(),"
        " rejection_reason = %(reason)s WHERE id = %(id)s AND status = 'pending_review'",
        {"reviewer": reviewer, "reason": reason, "id": claim_id},
    )


def list_approved_for_export(conn: psycopg.Connection) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT pc.*, ps.type AS source_type, ps.title AS source_title, ps.venue AS source_venue,
                   ps.year AS source_year, ps.url AS source_url, ps.verified AS source_verified
            FROM staging.pending_claim pc
            JOIN staging.pending_source ps ON ps.id = pc.source_id
            WHERE pc.status = 'approved'
            ORDER BY pc.source_id, pc.id
            """
        )
        return cur.fetchall()


def mark_exported(conn: psycopg.Connection, claim_ids: list[int]) -> None:
    if not claim_ids:
        return
    conn.execute(
        "UPDATE staging.pending_claim SET status = 'exported' WHERE id = ANY(%(ids)s)",
        {"ids": claim_ids},
    )
