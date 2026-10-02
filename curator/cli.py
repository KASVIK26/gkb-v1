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
from curator.genome.wheat_domains import classify_wheat_ref_genes
from curator.graph.bundle import KGBundle
from curator.graph.kg_files import load_curated_dir
from curator.graph.manifest import MANIFEST_PATH, write_manifest
from curator.graph.pg import GateError, create_release_schema, load_bundle
from curator.graph.promote import PromoteError, bridge_view_sql, current_release, promote, release_history
from curator.graph.scoring import score_bundle, summarize
from curator.graph.variety_import import variety_bundle
from curator.graph.vocab_entities import reference_bundle
from curator.graph import staging
from curator.lit.run_extraction import extract_paper
from curator.model.claims import Source

ROOT_DIR = Path(__file__).resolve().parents[1]
KG_CURATED_DIR = ROOT_DIR / "kg" / "curated"

app = typer.Typer(add_completion=False, help="AgriHub Genomic KB — build and load knowledge graph releases.")
kg_app = typer.Typer(add_completion=False, help="Knowledge-graph build/load commands.")
genome_app = typer.Typer(add_completion=False, help="Reference-genome extraction commands (Phase 4).")
lit_app = typer.Typer(add_completion=False, help="Literature search and grounded LLM extraction (Phase 5).")
app.add_typer(kg_app, name="kg")
app.add_typer(genome_app, name="genome")
app.add_typer(lit_app, name="lit")


def _build_bundle() -> KGBundle:
    """Reference entities (config/vocab/), notified varieties (config/sources/), and everything
    hand-curated in kg/curated/. The first two are generated fresh from their source files on
    every build, never hand-typed -- see vocab_entities.py and variety_import.py. Every claim then
    gets its computed score/tier/conflict (curator/graph/scoring.py), so no release ships unscored."""
    return score_bundle(KGBundle.merge(reference_bundle(), variety_bundle(), load_curated_dir(KG_CURATED_DIR)))


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
    typer.echo("confidence: " + json.dumps(summarize(bundle)))

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
        # The public.kg_* bridge views grant to Supabase's `anon` role; a plain Postgres has none.
        has_api_roles = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = 'anon'").fetchone() is not None
        try:
            result = promote(conn, schema, bridge_sql=bridge_view_sql() if has_api_roles else ())
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


@genome_app.command("classify-wheat-domains")
def classify_wheat_domains_cmd(
    refgenes_parquet: Path = typer.Option(
        DATA_INTERIM / "refgenes_wheat.parquet", help="Output of `genome build-refgenes` to enrich in place."
    ),
) -> None:
    """Fill in real InterPro-based NLR/RLK classification for wheat's ref_gene rows, by coordinate
    overlap against IWGSC's own gene annotation (NCBI's RefSeq GFF carries no domain data of its
    own -- see curator/genome/wheat_domains.py). Requires the IWGSC functional-annotation and
    gene-annotation files downloaded to data/raw/ (not committed; see PHASES.md for the URGI URLs).
    Overwrites refgenes_wheat.parquet in place; re-run `genome load-refgenes` afterwards."""
    df = classify_wheat_ref_genes(refgenes_parquet=refgenes_parquet)
    df.to_parquet(refgenes_parquet, index=False)
    nlr = df[df["is_nlr"]]
    typer.secho(
        f"Classified {len(df):,} wheat genes: {len(nlr):,} NLR/RLK ({len(nlr) / len(df):.2%})", fg=typer.colors.GREEN
    )


def _draft_yaml(source: Source, accepted: list) -> str:
    """Render accepted candidates as a kg/curated/-shaped draft (see kg/curated/README.md).

    This is deliberately just text for a human to read and paste in by hand -- Phase 5's own
    review UI (RESEARCH_ROADMAP.md 5.10) is the next step that would write kg/curated/ directly,
    and hasn't been built yet."""
    import yaml

    doc = {
        "sources": [{
            "id": source.id,
            "type": source.type.value,
            "title": source.title,
            "year": source.year,
            "venue": source.venue,
            "verified": source.verified,
        }],
        "claims": [
            {
                "type": item.claim.type.value,
                "subject": item.claim.subject_id,
                "object": item.claim.object_id,
                "qualifiers": item.claim.qualifiers,
                "status": "unreviewed",
                "evidence": [{
                    "source": item.evidence.source_id,
                    "method": item.evidence.method.value,
                    "locator": item.evidence.locator,
                    "quote": item.evidence.quote,
                    "extractor": item.evidence.extractor,
                }],
            }
            for item in accepted
        ],
    }
    return yaml.dump(doc, sort_keys=False, allow_unicode=True, default_flow_style=False)


@lit_app.command("extract")
def lit_extract_cmd(
    identifier: str = typer.Option(..., "--pmid", "--id", help="pmid:<digits> or doi:<doi> (verified live against Europe PMC)."),
    crop: str = typer.Option(..., help="wheat | soybean | chickpea"),
    model: str = typer.Option(None, help="Override the default OpenRouter model (for ablations)."),
) -> None:
    """Fetch one verified paper, extract candidate claims via a grounded LLM call, and print
    accepted candidates as a kg/curated/-shaped YAML draft (stdout) plus rejected candidates with
    their reasons (stderr). Writes nothing -- a human reviews and pastes accepted output by hand,
    exactly as every source in this project has been checked so far."""
    pmid_or_doi = identifier if ":" in identifier else f"pmid:{identifier}"
    result = extract_paper(pmid_or_doi, crop=crop, model=model)

    typer.echo(f"# {result.source.title} ({result.source.year}, {result.source.venue})", err=True)
    typer.echo(f"# {len(result.accepted)} accepted, {len(result.rejected)} rejected", err=True)
    for rejected in result.rejected:
        typer.secho(f"REJECTED: {rejected.reason}", fg=typer.colors.YELLOW, err=True)

    if result.accepted:
        typer.echo(_draft_yaml(result.source, result.accepted))
    else:
        typer.secho("No candidates survived grounding + normalization.", fg=typer.colors.YELLOW, err=True)


def _render_staged_yaml(rows: list[dict]) -> str:
    """Render approved staging.pending_claim rows (joined to their source) as a kg/curated/-shaped
    YAML draft -- same shape and rules as _draft_yaml, generalized to many sources/claims at once."""
    import yaml

    sources_by_id: dict[str, dict] = {}
    claims: list[dict] = []
    for row in rows:
        sources_by_id.setdefault(row["source_id"], {
            "id": row["source_id"],
            "type": row["source_type"],
            "title": row["source_title"],
            "year": row["source_year"],
            "venue": row["source_venue"],
            "verified": row["source_verified"],
        })
        claims.append({
            "type": row["claim_type"],
            "subject": row["subject_id"],
            "object": row["object_id"],
            "qualifiers": row["qualifiers"],
            "status": "unreviewed",
            "evidence": [{
                "source": row["source_id"],
                "method": row["method"],
                "locator": row["locator"],
                "quote": row["quote"],
                "extractor": row["extractor"],
            }],
        })
    doc = {"sources": list(sources_by_id.values()), "claims": claims}
    return yaml.dump(doc, sort_keys=False, allow_unicode=True, default_flow_style=False)


@lit_app.command("export-staged")
def lit_export_staged_cmd(
    out: Path = typer.Option(..., help="Output path, e.g. kg/curated/pending_2026_09_27.yaml"),
    database_url: str = typer.Option(
        ..., envvar="DATABASE_URL_DIRECT", help="Postgres connection string (direct/session pooler)."
    ),
) -> None:
    """Export every staging.pending_claim row with status='approved' into a kg/curated/-shaped YAML
    file, then mark those rows 'exported' (kept, not deleted -- an audit trail of what left staging
    and when). This automates the typing, not the judgment call: the file still needs a human
    `git add` + `agrihub kg build`/`load`/`promote` -- the exact same release gates every
    hand-written curated file already goes through are what actually prevents contamination, and
    nothing here bypasses them."""
    with psycopg.connect(database_url, autocommit=True) as conn:
        rows = staging.list_approved_for_export(conn)
        if not rows:
            typer.secho("No approved staged claims to export.", fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)

        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_render_staged_yaml(rows), encoding="utf-8")
        staging.mark_exported(conn, [row["id"] for row in rows])

    typer.secho(
        f"Exported {len(rows)} approved claim(s) from {len({r['source_id'] for r in rows})} source(s) to {out}",
        fg=typer.colors.GREEN,
    )
    typer.echo("Next: review the file, `git add` it, then `agrihub kg build` to check it passes the release gates.")


if __name__ == "__main__":
    app()
