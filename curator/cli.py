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


@kg_app.command("verify-quotes")
def verify_quotes_cmd(
    show_ok: bool = typer.Option(False, help="Also list quotes that verified exactly."),
) -> None:
    """Re-fetch every cited paper and check each stored quote against its text (needs network).

    Exits 1 if any quote is MISSING from a source whose text was available; 'no_text' (paywalled or
    unreachable) is reported but is not a failure, because it cannot be checked from here."""
    from curator.graph.quote_audit import audit_bundle, summarize as summarize_audit

    rows = audit_bundle(_build_bundle())
    typer.echo(json.dumps(summarize_audit(rows)))
    bad = [r for r in rows if r.status in ("missing", "fuzzy")]
    for row in rows if show_ok else bad:
        if row.status == "exact" and not show_ok:
            continue
        typer.echo(f"  [{row.status}] {row.claim_id} <- {row.source_id} ({row.locator}): {(row.quote or '')[:110]}")
    if any(r.status == "missing" for r in rows):
        raise typer.Exit(code=1)


@kg_app.command("ingest-candidates")
def ingest_candidates_cmd(
    candidates: Path = typer.Argument(..., exists=True, dir_okay=False, help="JSONL file: one candidate claim per line."),
    out: Path = typer.Option(None, help="Curated YAML to write (default: kg/incoming/<input name>.yaml)."),
) -> None:
    """Verify claim candidates made outside this repo (ChatGPT/Grok deep research) and write the survivors.

    Every candidate is checked against the real source (Europe PMC record and title, verbatim quote, entity
    resolution); nothing is written to kg/curated/. Outputs go next to --out: the YAML batch, a report, and the
    needs_review / unverifiable / rejected candidates with their reasons. Needs network."""
    from curator.lit.candidates import process_candidates, report_markdown, to_curated_yaml

    out = out or Path("kg/incoming") / f"{candidates.stem}.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    result = process_candidates(candidates.read_text(encoding="utf-8").splitlines(), bundle=_build_bundle())

    header = (
        f"Verified from {candidates.name} by `agrihub kg ingest-candidates`. NOT yet in kg/curated/:\n"
        "make a review sheet (agrihub kg review-sheet), have it filled, then agrihub kg apply-review."
    )
    out.write_text(to_curated_yaml(result, header), encoding="utf-8", newline="\n")
    out.with_suffix(".report.md").write_text(report_markdown(result), encoding="utf-8", newline="\n")
    for bucket in ("needs_review", "unverifiable", "rejected"):
        rows = [o for o in result.outcomes if o.bucket == bucket]
        if rows:
            lines = [json.dumps({"candidate_id": o.candidate_id, "reason": o.reason, "candidate": o.raw}, ensure_ascii=False) for o in rows]
            out.with_suffix(f".{bucket}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    typer.echo(json.dumps({"outcomes": result.counts(), "new_claims": len(result.claims), "new_sources": len(result.sources), "new_entities": len(result.entities)}))
    typer.echo(f"Wrote {out} (+ report). Next: agrihub kg review-sheet {out}")


@kg_app.command("import-aicrp-rust")
def import_aicrp_rust_cmd(
    url: str = typer.Argument(..., help="URL of an AICRP Wheat & Barley Crop Protection progress report (PDF)."),
    slug: str = typer.Option(..., help="Lowercase id fragment for the source, e.g. aicrp_crop_protection_2021_22."),
    title: str = typer.Option(..., help="Title as printed on the report."),
    year: int = typer.Option(..., help="Publication year of the report."),
    out: Path = typer.Option(None, help="Batch YAML to write (default: kg/incoming/<slug>.yaml)."),
) -> None:
    """Read the rust-screening tables of a Crop Protection report with a parser (no language model) and write a batch.

    Only rows for varieties the KB already has become claims; each is backed by the report's own row text. Needs network."""
    import yaml

    from curator.graph.aicrp_rust import claim_specs, parse_tables
    from curator.graph.quote_audit import fetch_url_text

    text = fetch_url_text(url)
    if text is None:
        typer.secho(f"Could not read {url}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    bundle = _build_bundle()
    rows = parse_tables(text)
    source_id = f"doc:{slug}"
    specs, unknown = claim_specs(rows, source_id=source_id, entities=bundle.entities)
    doc = {
        "sources": [] if source_id in {s.id for s in bundle.sources} else [{
            "id": source_id, "type": "official_document", "title": title, "year": year, "url": url, "verified": True,
            "venue": "ICAR-Indian Institute of Wheat and Barley Research, Karnal (AICRP on Wheat and Barley)"}],
        "entities": [], "claims": specs,
    }
    out = out or Path("kg/incoming") / f"{slug}.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    comment = [f"Read by parser:aicrp_rust@1 from {url}", "NOT yet in kg/curated/: agrihub kg review-sheet, then apply-review."]
    body = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=1000)
    out.write_text("".join(f"# {line}\n" for line in comment) + "\n" + body, encoding="utf-8", newline="\n")
    tables = sorted({(r.table_title, r.season) for r in rows})
    typer.echo(json.dumps({"tables_read": len(tables), "rows": len(rows), "claims": len(specs), "entries_not_in_kb": len(unknown)}))
    for t, _ in tables:
        typer.echo(f"  read: {t}")
    typer.echo(f"Wrote {out}. Next: agrihub kg review-sheet {out}")


@kg_app.command("import-aicrp-postulation")
def import_aicrp_postulation_cmd(
    url: str = typer.Argument(..., help="URL of an AICRP Wheat & Barley Crop Protection progress report (PDF)."),
    slug: str = typer.Option(..., help="Id fragment of the report's source, e.g. aicrp_crop_protection_2022_23 (the source must already be in the KB)."),
    out: Path = typer.Option(None, help="Batch YAML to write (default: kg/incoming/<slug>_postulation.yaml)."),
) -> None:
    """Read the Sr/Lr/Yr gene-postulation tables of a Crop Protection report with a parser (no language model) and write a batch.

    A row whose names do not add up to the count the report prints is skipped; only varieties the KB already has become claims. Needs network."""
    import yaml

    from curator.graph.aicrp_postulation import claim_specs, parse_tables
    from curator.graph.quote_audit import fetch_url_text

    source_id = f"doc:{slug}"
    bundle = _build_bundle()
    if source_id not in {s.id for s in bundle.sources}:
        typer.secho(f"{source_id} is not a source in the KB; import its rust tables first (kg import-aicrp-rust).", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    text = fetch_url_text(url)
    if text is None:
        typer.secho(f"Could not read {url}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    rows = parse_tables(text)
    specs, genes, unknown, skipped = claim_specs(rows, source_id=source_id, entities=bundle.entities)
    out = out or Path("kg/incoming") / f"{slug}_postulation.yaml"
    out.parent.mkdir(parents=True, exist_ok=True)
    comment = ["Read by parser:aicrp_postulation@1 from " + url, "NOT yet in kg/curated/: review, then copy."]
    body = yaml.safe_dump({"sources": [], "entities": genes, "claims": specs}, sort_keys=False, allow_unicode=True, width=1000)
    out.write_text("".join(f"# {line}\n" for line in comment) + "\n" + body, encoding="utf-8", newline="\n")
    typer.echo(json.dumps({"rows": len(rows), "rows_skipped": len(skipped), "claims": len(specs), "new_genes": len(genes), "entries_not_in_kb": len(unknown)}))
    for s in skipped:
        typer.echo(f"  skipped: {s}")
    typer.echo(f"Wrote {out}.")


@kg_app.command("publish-files")
def publish_files_cmd(
    release: str = typer.Option(..., help="Release tag, e.g. 2026_10_35."),
    crosswalk_out: Path = typer.Option(Path("kg/ids_crosswalk.tsv"), help="Shared ID crosswalk for the other AgriHub products."),
    dictionary_out: Path = typer.Option(Path("docs/DATA_DICTIONARY.md"), help="Data dictionary generated from the models."),
    metadata_out: Path = typer.Option(Path("kg/metadata.jsonld"), help="schema.org Dataset description."),
) -> None:
    """Write the publication files that must not drift from the code: the ID crosswalk (task 11.4), the data dictionary and the dataset metadata (no network)."""
    from curator.graph.publish import crosswalk_tsv, data_dictionary_markdown, metadata_json

    bundle = _build_bundle()
    for path, text in ((crosswalk_out, crosswalk_tsv(bundle)), (dictionary_out, data_dictionary_markdown()), (metadata_out, metadata_json(bundle, release=release))):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        typer.echo(f"Wrote {path}")


@kg_app.command("analytics")
def analytics_cmd(
    out: Path = typer.Option(Path("docs/ANALYTICS.md"), help="Markdown report to write."),
    release: str = typer.Option("", help="Release tag to print in the title (informational)."),
) -> None:
    """Write the research tables computed from the curated graph (no network): multi-rust donors, observed susceptibility, rust-gene deployment by zone,
    dominant pathotypes by state and season, and the widely recommended varieties with the most unrecorded disease readings."""
    from curator.graph.analytics import analytics, to_markdown

    result = analytics(_build_bundle())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_markdown(result, release=release), encoding="utf-8", newline="\n")
    typer.echo(json.dumps({"multi_rust_donors": len(result["multi_rust_donors"]), "zones_with_gene_deployment": len(result["gene_deployment"]),
                           "dominant_pathotype_rows": len(result["dominant_pathotypes"]), "untested_varieties": len(result["recommended_but_untested"])}))
    typer.echo(f"Wrote {out}.")


@kg_app.command("qc")
def qc_cmd(
    out: Path = typer.Option(Path("docs/QC_REPORT.md"), help="Markdown report to write."),
    release: str = typer.Option("", help="Release tag to print in the title (informational)."),
) -> None:
    """Write the QC report and the scoring sensitivity analysis for the curated graph (no network).

    Provenance integrity, confidence tiers, coverage per crop and disease, structural checks, distance to the roadmap targets, and how many
    claims change tier when the scoring constants change."""
    from curator.graph.qc import qc_report, sensitivity, to_markdown

    bundle = _build_bundle()
    report, sens = qc_report(bundle), sensitivity(bundle)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_markdown(report, sens, release=release), encoding="utf-8", newline="\n")
    typer.echo(json.dumps({"claims": report["provenance"]["claims"], "tiers": report["confidence"]["tiers"], "conflicts": report["confidence"]["conflicts"],
                           "gaps": len(report["disease_gaps"]), "max_share_changing_tier": max(x["share_changing"] for x in sens["scenarios"])}))
    typer.echo(f"Wrote {out}.")


@kg_app.command("review-sheet")
def review_sheet_cmd(
    batch: Path = typer.Argument(..., exists=True, dir_okay=False, help="A kg/incoming/*.yaml batch from ingest-candidates."),
    out: Path = typer.Option(None, help="CSV to write (default: next to the batch, .review.csv)."),
    rate: float = typer.Option(0.1, min=0.0, max=1.0, help="Share of rows in the mandatory sample (minimum 10 rows)."),
    seed: int = typer.Option(7, help="Seed for the sample."),
    everything: bool = typer.Option(False, help="Mark every row as in-sample (review the whole batch)."),
) -> None:
    """Write the spreadsheet a crop expert fills in: plain-words claim, verbatim quote, source link, verdict column."""
    from curator.lit.review_sheet import make_sheet

    out = out or batch.with_suffix(".review.csv")
    counts = make_sheet(batch, _build_bundle(), out, rate=rate, seed=seed, everything=everything)
    typer.echo(json.dumps(counts))
    typer.echo(f"Wrote {out}. Send it to the reviewer (opens in Excel / Google Sheets); then: agrihub kg apply-review {batch} {out} --reviewer NAME")


@kg_app.command("apply-review")
def apply_review_cmd(
    batch: Path = typer.Argument(..., exists=True, dir_okay=False),
    sheet: Path = typer.Argument(..., exists=True, dir_okay=False, help="The filled-in review CSV."),
    reviewer: str = typer.Option(None, help="Default reviewer name for OK rows that have none in the sheet."),
    out: Path = typer.Option(None, help="Curated YAML to write (default: kg/curated/<batch name>.yaml)."),
) -> None:
    """Apply a filled review sheet: enforce the sample gate, stamp reviewers, hold back what was not confirmed."""
    from curator.lit.review_sheet import ReviewError, apply_review

    out = out or Path("kg/curated") / batch.name
    try:
        result = apply_review(batch, sheet, out, reviewer=reviewer)
    except ReviewError as exc:
        typer.secho(f"Not applied: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps({"claims_written": result.accepted_claims, "of_which_reviewed": result.reviewed_claims,
                           "sample": result.sample_n, "sample_not_confirmed": result.sample_not_ok, "held_back": len(result.held)}))
    for row in result.held:
        typer.echo(f"  held back [{row['why']}] {row['row_id']}: {row['claim'][:90]} {row['comment']}")
    typer.echo(f"Wrote {out}. Next: agrihub kg build && agrihub kg verify-quotes")


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


@lit_app.command("find")
def lit_find_cmd(
    a: list[str] = typer.Option(..., "--a", help="First thing to find, e.g. a variety. Repeat for name variants."),
    b: list[str] = typer.Option(..., "--b", help="Second thing, e.g. a gene. Repeat for name variants."),
    max_papers: int = typer.Option(15, help="How many matching open-access papers to read."),
) -> None:
    """Print verbatim sentences / table rows where both things appear together in open-access papers.

    A finder, not an extractor: nothing is paraphrased or generated, so every line is a real substring of a
    real paper. What it means (carries? lacks? merely cited?) is for a human to judge before it becomes a claim."""
    from curator.lit.find_evidence import find_evidence

    hits = find_evidence(a, b, max_papers=max_papers)
    if not hits:
        typer.echo("No co-occurring text found in open-access papers.")
        return
    current = None
    for hit in hits:
        if hit.source_id != current:
            current = hit.source_id
            typer.echo(f"\n[{hit.source_id} | {hit.year} | {hit.journal}] {hit.title}")
        typer.echo(f"  ({hit.locator}) {hit.text}")


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
