-- Enable the Postgres extensions this project needs, in Supabase's convention (extensions
-- schema, not public). Safe to run more than once (IF NOT EXISTS everywhere).
--
-- What each is for:
--   pg_trgm  - fuzzy/typo-tolerant search on variety, gene and disease names (used by the
--              trigram indexes in db/release_schema.sql, e.g. entity_name_trgm_idx).
--   postgis  - agro-zone and district geometries, "which zone is this farmer in" lookups
--              (db/release_schema_postgis.sql, Phase 3+). Enabled now since it is cheap and
--              zone data is coming soon; the base KG schema does not require it.
--
-- NOT included here (do this later, when actually needed):
--   pg_cron  - enable via Dashboard -> Database -> Extensions (it needs a server restart the
--              first time, which the dashboard handles; plain CREATE EXTENSION from the SQL
--              editor may fail with a permissions error). Cron jobs come with Phase 8/11
--              (sensor rollups, KG-release housekeeping).
--   vector (pgvector) - later, for semantic search (TECH_STACK.md ADR-2).

create schema if not exists extensions;

create extension if not exists pg_trgm with schema extensions;
create extension if not exists postgis with schema extensions;

-- Supabase's built-in roles need to be able to use objects in the extensions schema (operator
-- classes, functions). This is usually already the case on a fresh project, but grant it
-- explicitly so this migration is a complete, self-contained fix.
grant usage on schema extensions to postgres, anon, authenticated, service_role;
