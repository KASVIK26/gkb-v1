-- Spatial add-on for a KG release schema. Needs PostGIS, enabled by
-- supabase/migrations/20260925081644_enable_extensions.sql.
-- Run after release_schema.sql with the same search_path (or paste standalone: the geometry
-- type below is schema-qualified so it does not depend on search_path).

CREATE TABLE zone_geom (
    entity_id   text PRIMARY KEY REFERENCES entity (id) ON DELETE CASCADE,
    geom        extensions.geometry(MultiPolygon, 4326) NOT NULL,
    source_id   text REFERENCES source (id)
);
CREATE INDEX zone_geom_gix ON zone_geom USING gist (geom);
