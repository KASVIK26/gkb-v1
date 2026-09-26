-- KG release schema (one schema per release, e.g. kg_2026_10_1). See TECH_STACK.md ADR-7.
-- The loader runs this with:  SET search_path = <release_schema>, extensions, public;
-- Requires pg_trgm, enabled by supabase/migrations/20260925081644_enable_extensions.sql.
-- Operator classes below are schema-qualified (extensions.gin_trgm_ops) so this file also
-- works if pasted into the SQL editor without first setting search_path.
-- Plain PostgreSQL only; PostGIS objects live in release_schema_postgis.sql.

CREATE TABLE source (
    id          text PRIMARY KEY,
    type        text NOT NULL CHECK (type IN ('publication', 'dataset', 'trial_report', 'catalogue',
                                              'official_document', 'curated_vocab', 'test')),
    title       text NOT NULL,
    year        int,
    venue       text,
    url         text,
    license     text,
    verified    boolean NOT NULL DEFAULT false
);

CREATE TABLE entity (
    id          text PRIMARY KEY,
    type        text NOT NULL,
    crop        text CHECK (crop IN ('wheat', 'soybean', 'chickpea')),
    name        text NOT NULL,
    name_i18n   jsonb NOT NULL DEFAULT '{}',
    props       jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX entity_type_crop_idx ON entity (type, crop);
CREATE INDEX entity_name_trgm_idx ON entity USING gin (name extensions.gin_trgm_ops);

CREATE TABLE entity_synonym (
    entity_id   text NOT NULL REFERENCES entity (id) ON DELETE CASCADE,
    synonym     text NOT NULL,
    PRIMARY KEY (entity_id, synonym)
);
CREATE INDEX entity_synonym_trgm_idx ON entity_synonym USING gin (synonym extensions.gin_trgm_ops);

CREATE TABLE claim (
    id          text PRIMARY KEY,
    type        text NOT NULL,
    subject_id  text NOT NULL REFERENCES entity (id),
    object_id   text NOT NULL REFERENCES entity (id),
    qualifiers  jsonb NOT NULL DEFAULT '{}',
    status      text NOT NULL CHECK (status IN ('unreviewed', 'reviewed', 'predicted', 'rejected')),
    score       real CHECK (score BETWEEN 0 AND 1),
    tier        char(1) CHECK (tier IN ('A', 'B', 'C', 'D')),
    conflict    boolean NOT NULL DEFAULT false
);
CREATE INDEX claim_subject_idx ON claim (subject_id, type);
CREATE INDEX claim_object_idx ON claim (object_id, type);
CREATE INDEX claim_qualifiers_idx ON claim USING gin (qualifiers);

CREATE TABLE evidence (
    id          text PRIMARY KEY,
    claim_id    text NOT NULL REFERENCES claim (id) ON DELETE CASCADE,
    source_id   text NOT NULL REFERENCES source (id),
    method      text NOT NULL,
    extractor   text NOT NULL,
    locator     text,
    quote       text,
    reviewer    text,
    reviewed_at timestamptz,
    weight      real
);
CREATE INDEX evidence_claim_idx ON evidence (claim_id);
CREATE INDEX evidence_source_idx ON evidence (source_id);

-- Full reference gene models (all protein-coding genes). Only candidate/anchored genes are
-- also entities (type 'RefGene'); this table is for interval queries.
CREATE TABLE ref_gene (
    locus_id    text PRIMARY KEY,
    crop        text NOT NULL CHECK (crop IN ('wheat', 'soybean', 'chickpea')),
    assembly    text NOT NULL,
    chromosome  text NOT NULL,
    start_bp    bigint NOT NULL,
    end_bp      bigint NOT NULL CHECK (end_bp >= start_bp),
    strand      char(1) NOT NULL CHECK (strand IN ('+', '-', '.')),
    description text,
    domains     text[] NOT NULL DEFAULT '{}',
    is_nlr      boolean NOT NULL DEFAULT false,
    nlr_class   text
);
CREATE INDEX ref_gene_pos_idx ON ref_gene (crop, assembly, chromosome, start_bp);

-- ─────────────── typed views: one per claim type (the "edges") ───────────────
-- Queries and the API read these, never raw jsonb. They expose only citable claims
-- (reviewed or unreviewed); rejected claims and model predictions are excluded.

CREATE VIEW v_variety_reaction AS
SELECT c.id AS claim_id, c.subject_id AS variety_id, c.object_id AS disease_id,
       c.qualifiers ->> 'reaction' AS reaction,
       c.qualifiers ->> 'stage' AS stage,
       c.qualifiers ->> 'pathotype_id' AS pathotype_id,
       c.qualifiers ->> 'location' AS location,
       c.qualifiers ->> 'season' AS season,
       c.qualifiers ->> 'score_raw' AS score_raw,
       c.status, c.score, c.tier, c.conflict
FROM claim c WHERE c.status IN ('reviewed', 'unreviewed') AND c.type = 'VARIETY_REACTION';

CREATE VIEW v_variety_carries AS
SELECT c.id AS claim_id, c.subject_id AS variety_id, c.object_id AS gene_id,
       c.qualifiers ->> 'method' AS method, c.qualifiers ->> 'allele' AS allele,
       c.status, c.score, c.tier
FROM claim c WHERE c.status IN ('reviewed', 'unreviewed') AND c.type = 'VARIETY_CARRIES_GENE';

CREATE VIEW v_variety_zone AS
SELECT c.id AS claim_id, c.subject_id AS variety_id, c.object_id AS zone_id,
       c.qualifiers ->> 'season' AS season, c.qualifiers ->> 'sowing' AS sowing,
       c.qualifiers ->> 'water_regime' AS water_regime, c.status, c.tier
FROM claim c WHERE c.status IN ('reviewed', 'unreviewed') AND c.type = 'VARIETY_RECOMMENDED_FOR_ZONE';

CREATE VIEW v_variety_parent AS
SELECT c.id AS claim_id, c.subject_id AS variety_id, c.object_id AS parent_id,
       c.qualifiers ->> 'role' AS role, c.status, c.tier
FROM claim c WHERE c.status IN ('reviewed', 'unreviewed') AND c.type = 'VARIETY_DERIVED_FROM';

CREATE VIEW v_gene_resistance AS
SELECT c.id AS claim_id, c.subject_id AS gene_id, c.object_id AS disease_id,
       c.qualifiers ->> 'resistance_type' AS resistance_type,
       c.qualifiers ->> 'spectrum' AS spectrum, c.status, c.score, c.tier
FROM claim c WHERE c.status IN ('reviewed', 'unreviewed') AND c.type = 'GENE_CONFERS_RESISTANCE';

CREATE VIEW v_gene_pathotype AS
SELECT c.id AS claim_id, c.subject_id AS gene_id, c.object_id AS pathotype_id,
       c.qualifiers ->> 'outcome' AS outcome,
       (c.qualifiers ->> 'year')::int AS year,
       c.qualifiers ->> 'region' AS region, c.status, c.tier
FROM claim c WHERE c.status IN ('reviewed', 'unreviewed') AND c.type = 'GENE_PATHOTYPE_INTERACTION';

CREATE VIEW v_gene_located_at AS
SELECT c.id AS claim_id, c.subject_id AS gene_id, c.object_id AS ref_gene_id,
       c.qualifiers ->> 'method' AS method, c.qualifiers ->> 'assembly' AS assembly,
       (c.qualifiers ->> 'identity_pct')::real AS identity_pct, c.status, c.tier
FROM claim c WHERE c.status IN ('reviewed', 'unreviewed') AND c.type = 'GENE_LOCATED_AT';

CREATE VIEW v_qtl_association AS
SELECT c.id AS claim_id, c.subject_id AS qtl_id, c.object_id AS disease_id,
       c.qualifiers ->> 'stage' AS stage,
       c.qualifiers ->> 'left_marker' AS left_marker, c.qualifiers ->> 'right_marker' AS right_marker,
       c.qualifiers ->> 'assembly' AS assembly,
       (c.qualifiers ->> 'start_bp')::bigint AS start_bp, (c.qualifiers ->> 'end_bp')::bigint AS end_bp,
       (c.qualifiers ->> 'lod')::real AS lod, (c.qualifiers ->> 'pve_pct')::real AS pve_pct,
       c.qualifiers ->> 'population' AS population, c.status, c.tier
FROM claim c WHERE c.status IN ('reviewed', 'unreviewed') AND c.type = 'QTL_ASSOCIATION';

CREATE VIEW v_qtl_contains AS
SELECT c.id AS claim_id, c.subject_id AS qtl_id, c.object_id AS ref_gene_id,
       c.qualifiers ->> 'assembly' AS assembly, (c.qualifiers ->> 'rank')::int AS rank, c.status
FROM claim c WHERE c.status IN ('reviewed', 'unreviewed') AND c.type = 'QTL_CONTAINS_REFGENE';

CREATE VIEW v_marker_linkage AS
SELECT c.id AS claim_id, c.subject_id AS marker_id, c.object_id AS target_id,
       (c.qualifiers ->> 'distance_cm')::real AS distance_cm,
       coalesce((c.qualifiers ->> 'diagnostic')::boolean, false) AS diagnostic, c.status, c.tier
FROM claim c WHERE c.status IN ('reviewed', 'unreviewed') AND c.type = 'MARKER_LINKAGE';

CREATE VIEW v_disease_pathogen AS
SELECT c.id AS claim_id, c.subject_id AS disease_id, c.object_id AS pathogen_id, c.status
FROM claim c WHERE c.status IN ('reviewed', 'unreviewed') AND c.type = 'DISEASE_CAUSED_BY';

CREATE VIEW v_pathotype_pathogen AS
SELECT c.id AS claim_id, c.subject_id AS pathotype_id, c.object_id AS pathogen_id, c.status
FROM claim c WHERE c.status IN ('reviewed', 'unreviewed') AND c.type = 'PATHOTYPE_VARIANT_OF';

CREATE VIEW v_pathotype_prevalence AS
SELECT c.id AS claim_id, c.subject_id AS pathotype_id, c.object_id AS zone_id,
       ARRAY(SELECT jsonb_array_elements_text(c.qualifiers -> 'years')::int) AS years,
       (c.qualifiers ->> 'frequency_pct')::real AS frequency_pct, c.status, c.tier
FROM claim c WHERE c.status IN ('reviewed', 'unreviewed') AND c.type = 'PATHOTYPE_PREVALENCE';

CREATE VIEW v_disease_trigger AS
SELECT c.id AS claim_id, c.subject_id AS disease_id, c.object_id AS trigger_id,
       e.props ->> 'phase' AS phase,
       (e.props ->> 'bbch_from')::int AS bbch_from, (e.props ->> 'bbch_to')::int AS bbch_to,
       e.props -> 'conditions' AS conditions, c.status, c.tier
FROM claim c JOIN entity e ON e.id = c.object_id
WHERE c.status IN ('reviewed', 'unreviewed') AND c.type = 'DISEASE_ENV_TRIGGER';

CREATE VIEW v_disease_advisory AS
SELECT c.id AS claim_id, c.subject_id AS disease_id, c.object_id AS advisory_id, c.status, c.tier
FROM claim c WHERE c.status IN ('reviewed', 'unreviewed') AND c.type = 'DISEASE_MANAGED_BY';

-- Claims usable for answers: not rejected, not model predictions.
CREATE VIEW v_claim_citable AS
SELECT * FROM claim WHERE status IN ('reviewed', 'unreviewed');
