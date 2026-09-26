"""agrihub CLI: build and load knowledge-graph releases.

    agrihub kg build              validate kg/ and report what a release would contain
    agrihub kg load --release X   build, then load into a fresh `kg_X` Postgres schema

The database connection always uses the DIRECT (session pooler) URL, not the transaction
pooler — schema creation and bulk COPY/INSERT need a stable session (TECH_STACK.md ADR-2).
"""

from __future__ import annotations

import json
from pathlib import Path

import psycopg
import typer

from curator.genome.build import DATA_INTERIM, build_all, summarize
from curator.genome.load import load_ref_genes
from curator.graph.bundle import KGBundle
from curator.graph.kg_files import load_curated_dir
from curator.graph.manifest import MANIFEST_PATH, write_manifest
from curator.graph.pg import GateError, create_release_schema, load_bundle
from curator.graph.promote import PromoteError, current_release, promote, release_history
from curator.graph.variety_import import variety_bundle
from curator.graph.vocab_entities import reference_bundle

ROOT_DIR = Path(__file__).resolve().parents[1]
KG_CURATED_DIR = ROOT_DIR / "kg" / "curated"

app = typer.Typer(add_completion=False, help="AgriHub Genomic KB — build and load knowledge graph releases.")
kg_app = typer.Typer(add_completion=False, help="Knowledge-graph build/load commands.")
genome_app = typer.Typer(add_completion=False, help="Reference-genome extraction commands (Phase 4).")
app.add_typer(kg_app, name="kg")
app.add_typer(genome_app, name="genome")


def _build_bundle() -> KGBundle:
    """Reference entities (config/vocab/), notified varieties (config/sources/), and everything
    hand-curated in kg/curated/. The first two are generated fresh from their source files on
    every build, never hand-typed -- see vocab_entities.py and variety_import.py."""
    return KGBundle.merge(reference_bundle(), variety_bundle(), load_curated_dir(KG_CURATED_DIR))


def _report_counts(bundle: KGBundle) -> dict[str, int]:
    return {
        "entities": len(bundle.entities),
        "sources": len(bundle.sources),
        "claims": len(bundle.claims),
        "evidence": len(bundle.evidence),
    }


@kg_app.command("build")
def build(allow_test_sources: bool = typer.Option(False, help="Allow SourceType.TEST sources (for local testing only).")) -> None:
    """Validate every kg/ source file and report what a release would contain. Loads nothing."""
    bundle = _build_bundle()
    typer.echo(json.dumps(_report_counts(bundle), indent=2))

    errors = bundle.gate_errors(allow_test_sources=allow_test_sources)
    if errors:
        typer.secho(f"\n{len(errors)} release gate error(s):", fg=typer.colors.RED)
        for err in errors[:50]:
            typer.echo(f"  - {err}")
        raise typer.Exit(code=1)
    typer.secho("\nBuild OK - all release gates passed.", fg=typer.colors.GREEN)


@kg_app.command("load")
def load(
    release: str = typer.Option(..., help="Release tag, e.g. 2026_10_1 -> creates schema kg_2026_10_1"),
    database_url: str = typer.Option(
        ..., envvar="DATABASE_URL_DIRECT", help="Postgres connection string (direct/session pooler, not the transaction pooler)."
    ),
    postgis: bool = typer.Option(False, help="Also create the PostGIS zone-map tables (db/release_schema_postgis.sql)."),
    manifest_path: Path = typer.Option(
        MANIFEST_PATH, help="Where to write the build manifest (checksums, git SHA, counts). Tests override this."
    ),
) -> None:
    """Build, validate, and load a brand-new KG release schema. Refuses to overwrite an existing one."""
    schema = f"kg_{release}"
    bundle = _build_bundle()

    errors = bundle.gate_errors()
    if errors:
        typer.secho(f"{len(errors)} release gate error(s) — nothing was loaded:", fg=typer.colors.RED)
        for err in errors[:50]:
            typer.echo(f"  - {err}")
        raise typer.Exit(code=1)

    with psycopg.connect(database_url, autocommit=True) as conn:
        typer.echo(f"Creating schema {schema} ...")
        create_release_schema(conn, schema, postgis=postgis)
        try:
            counts = load_bundle(conn, schema, bundle)
        except GateError as exc:
            typer.secho(f"Load failed, dropping incomplete schema {schema}:\n{exc}", fg=typer.colors.RED)
            conn.execute(f"DROP SCHEMA {schema} CASCADE")
            raise typer.Exit(code=1) from exc

    manifest = write_manifest(bundle, release=release, path=manifest_path)
    typer.secho(f"Loaded release '{schema}': {json.dumps(counts)}", fg=typer.colors.GREEN)
    typer.echo(f"Manifest written to {manifest_path} (git_sha={manifest['git_sha']}, dirty={manifest['git_dirty']})")
    typer.echo(f"Note: this does not repoint kg_current — run `agrihub kg promote --release {release}` to go live.")


@kg_app.command("promote")
def promote_cmd(
    release: str = typer.Option(..., help="Release tag to make live, e.g. 2026_10_2 -> promotes schema kg_2026_10_2"),
    database_url: str = typer.Option(
        ..., envvar="DATABASE_URL_DIRECT", help="Postgres connection string (direct/session pooler, not the transaction pooler)."
    ),
) -> None:
    """Atomically repoint kg_current at an already-loaded release schema."""
    schema = f"kg_{release}"
    with psycopg.connect(database_url, autocommit=True) as conn:
        try:
            result = promote(conn, schema)
        except PromoteError as exc:
            typer.secho(f"Promotion refused: {exc}", fg=typer.colors.RED)
            raise typer.Exit(code=1) from exc
    typer.secho(f"kg_current now points at '{schema}': {json.dumps(result)}", fg=typer.colors.GREEN)


@kg_app.command("current")
def current_cmd(
    database_url: str = typer.Option(
        ..., envvar="DATABASE_URL_DIRECT", help="Postgres connection string (direct/session pooler, not the transaction pooler)."
    ),
    history: bool = typer.Option(False, "--history", help="Show the full promotion history, not just the current release."),
) -> None:
    """Show which release kg_current points at (and optionally the full switchover history)."""
    with psycopg.connect(database_url, autocommit=True) as conn:
        if history:
            for row in release_history(conn):
                typer.echo(f"{row['switched_at']}  {row['release']}")
        else:
            release = current_release(conn)
            typer.echo(release if release else "(no release has been promoted yet)")


@genome_app.command("build-refgenes")
def build_refgenes(
    out_dir: Path = typer.Option(DATA_INTERIM, help="Where to write refgenes_<crop>.parquet"),
) -> None:
    """Parse the 3 real genome files in data/raw/ into per-crop RefGene Parquet files, with
    domain-based NLR/RLK classification for chickpea/soybean (see curator/genome/refgenes.py's
    module docstring for why wheat isn't classified the same way)."""
    frames = build_all(out_dir=out_dir)
    typer.echo(f"Wrote {len(frames)} Parquet file(s) to {out_dir}")
    typer.echo(summarize(frames))


@genome_app.command("load-refgenes")
def load_refgenes(
    release: str = typer.Option(..., help="Release tag whose ref_gene table to load into, e.g. 2026_10_14"),
    database_url: str = typer.Option(
        ..., envvar="DATABASE_URL_DIRECT", help="Postgres connection string (direct/session pooler)."
    ),
    parquet_dir: Path = typer.Option(DATA_INTERIM, help="Directory with refgenes_<crop>.parquet files."),
) -> None:
    """Load refgenes_<crop>.parquet (from `genome build-refgenes`) into an existing release
    schema's ref_gene table. Independent of `kg load` -- run this after it, against the same or
    any other already-created release schema."""
    schema = f"kg_{release}"
    with psycopg.connect(database_url, autocommit=True) as conn:
        counts = load_ref_genes(conn, schema, parquet_dir=parquet_dir)
    typer.secho(f"Loaded ref_gene rows into {schema}: {json.dumps(counts)}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
