-- Staging area for the paper-extraction review pipeline (docs/plans: paper-extraction review
-- pipeline + graph visualizer, 2026-09-27). Deliberately its own schema, NOT inside any
-- kg_<release> schema: curator/graph/promote.py's _relations_in_schema() only ever inspects the
-- one schema named by its release_schema argument (via pg_catalog, not a name-based filter), so
-- a schema kept alongside kg_meta (same precedent -- see curator/graph/promote.py's
-- ensure_meta_schema) is invisible to promote() by construction. It is never exposed to
-- PostgREST/anon; only the api/ service (using DATABASE_URL_DIRECT, the same credential the
-- Python pipeline already uses locally) reads or writes it.
--
-- Rows here are NOT raw LLM output. By the time a candidate reaches staging.pending_claim it has
-- already passed curator.extract.ground.ground_candidate (quote verified against the fetched
-- text) and curator.extract.normalize.build_claim_candidate (subject/object resolved to real
-- canonical entity IDs, or rejected) -- these columns hold that already-validated Claim's own
-- fields, not free text. The actual non-contamination guarantee is downstream of this table: the
-- `agrihub lit export-staged` command (curator/cli.py) only ever emits kg/curated/*.yaml, which
-- `agrihub kg build` validates through the exact same curator/graph/bundle.py::gate_errors() every
-- hand-curated file already goes through, unmodified.

CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE staging.pending_source (
    id          text PRIMARY KEY,        -- same pmid:<digits> / doi:<doi> grammar as curator.model.claims.Source
    type        text NOT NULL,
    title       text NOT NULL,
    year        int,
    venue       text,
    url         text,
    license     text,
    verified    boolean NOT NULL DEFAULT true,  -- rows only ever inserted here after a live Europe PMC check
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE staging.pending_claim (
    id                bigserial PRIMARY KEY,
    claim_type        text NOT NULL,
    subject_id        text NOT NULL,
    object_id         text NOT NULL,
    qualifiers        jsonb NOT NULL DEFAULT '{}',
    status            text NOT NULL DEFAULT 'pending_review'
                        CHECK (status IN ('pending_review', 'approved', 'rejected', 'exported')),
    source_id         text NOT NULL REFERENCES staging.pending_source (id),
    method            text NOT NULL,
    extractor         text NOT NULL,
    locator           text,
    quote             text,
    llm_model         text,
    grounding_score   real,   -- rapidfuzz partial_ratio at extraction time (0-100), shown to the reviewer
    source_relevance  jsonb,  -- {"relevant": bool, "notes": "..."} -- an LLM opinion, never treated as fact
    reviewer          text,
    reviewed_at       timestamptz,
    rejection_reason  text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    CHECK ((status = 'rejected') = (rejection_reason IS NOT NULL)),
    CHECK ((status IN ('approved', 'rejected')) = (reviewer IS NOT NULL AND reviewed_at IS NOT NULL))
);
CREATE INDEX pending_claim_status_idx ON staging.pending_claim (status);
CREATE INDEX pending_claim_source_idx ON staging.pending_claim (source_id);

-- No GRANT to anon/authenticated anywhere in this file, on purpose -- this schema is deliberately
-- unreachable from PostgREST. The api/ service connects with the same direct Postgres credential
-- (DATABASE_URL_DIRECT) the curator pipeline already uses, not through the REST layer.
