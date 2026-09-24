"""Orchestrate the full data pipeline: registry -> parse -> extract -> load."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from curator.db import DBDriver
from curator.init_constraints import create_constraints
from curator.parsers.gbff_parser import GBFFFormatError, parse_gbff
from curator.parsers.gff_parser import parse_gff3
from curator.parsers.genomic_integration import load_chromosome_mappings
from curator.validator import ValidationError


ROOT_DIR = Path(__file__).resolve().parents[1]
DATASETS_PATH = ROOT_DIR / "config" / "datasets.yaml"
REVIEW_QUEUE_PATH = ROOT_DIR / "data" / "review_queue.json"


def load_dataset_registry(path: Path = DATASETS_PATH) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        registry = yaml.safe_load(handle) or {}
    if not isinstance(registry, dict):
        raise ValidationError("Dataset registry must be a mapping at the top level.")
    registry.setdefault("datasets", [])
    return registry


def select_downloaded_datasets(registry: dict) -> list:
    datasets = registry.get("datasets", [])
    if not isinstance(datasets, list):
        raise ValidationError("The 'datasets' key must contain a list.")
    return [d for d in datasets if d.get("status") == "downloaded"]


def update_dataset_status(dataset_id: str, new_status: str, path: Path = DATASETS_PATH) -> None:
    """Flip a dataset status in datasets.yaml. Raises KeyError if dataset_id not found."""
    with path.open("r", encoding="utf-8") as handle:
        registry = yaml.safe_load(handle) or {}
    updated = False
    for entry in registry.get("datasets", []):
        if entry.get("id") == dataset_id:
            entry["status"] = new_status
            updated = True
            break
    if not updated:
        raise KeyError("Dataset '{}' not found in registry at {}".format(dataset_id, path))
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(registry, handle, default_flow_style=False, allow_unicode=True, sort_keys=False)


def append_to_review_queue(record: dict, error_message: str, path: Path = REVIEW_QUEUE_PATH) -> None:
    """Append a failing record + error to the review queue JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list = []
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as fh:
                existing = json.load(fh)
        except (json.JSONDecodeError, OSError):
            existing = []
    existing.append({"status": "pending", "error": error_message, "record": record})
    with path.open("w", encoding="utf-8") as fh:
        json.dump(existing, fh, indent=2, ensure_ascii=False)



def process_dataset(dataset: dict) -> dict:
    """Validate a GFF3 dataset and enrich the Crop node with genome statistics.

    GFF3 reference annotation files use systematic locus IDs (e.g., LOC123...,
    Glyma.01G...) that do not map to curated resistance gene names (Sr33, Yr18,
    Rps1, ...). Gene-level resistance knowledge must come from:
      - curator/seed_loader.py  (the 22 curated seed resistance genes)
      - curator/extractors/paper_extractor.py  (AI extraction from papers)

    This function instead reads the GFF3, counts genes and chromosomes, and
    stores those counts as properties on the Crop node in Neo4j.
    """
    result = {
        "id": dataset["id"],
        "crop": dataset["crop"],
        "genes_parsed": 0,
        "resistance_genes": 0,
        "genes_loaded": 0,
        "error": None,
    }
    try:
        local_path = dataset["local_path"]
        dataset_type = dataset.get("type", "")
        gff_exts  = (".gff.gz", ".gff3.gz", ".gff", ".gff3")
        gbff_exts = (".gbff.gz", ".gbff", ".gb.gz", ".gb")
        is_gff   = any(local_path.endswith(e) for e in gff_exts)
        is_gbff  = any(local_path.endswith(e) for e in gbff_exts)
        is_annotation = dataset_type == "gene_annotation"

        if not (is_gff or is_gbff or is_annotation):
            result["error"] = (
                "Skipped -- unrecognised file format "
                "(type='{}', path='{}'). "
                "Supported: GFF3 (.gff/.gff3/.gff.gz/.gff3.gz) or "
                "GBFF (.gbff/.gbff.gz). "
                "Set type: gene_annotation in datasets.yaml."
            ).format(dataset_type, local_path)
            return result

        genome_path = Path(local_path)
        if not genome_path.exists():
            result["error"] = "File not found: {}".format(genome_path)
            return result

        chromosome_mappings = None
        if dataset.get("assembly_report"):
            report_path = Path(dataset["assembly_report"])
            if report_path.exists():
                chromosome_mappings = load_chromosome_mappings(report_path)
            else:
                print("    WARNING: Assembly report not found at {} -- "
                      "chromosome labels will be raw sequence IDs".format(report_path))

        # ── Choose parser based on file extension ─────────────────────────────
        if is_gbff:
            try:
                genes = parse_gbff(genome_path, chromosome_mappings)
                fmt = "GBFF"
            except GBFFFormatError as exc:
                result["error"] = str(exc)
                return result
        else:
            genes = parse_gff3(genome_path, chromosome_mappings)
            fmt = "GFF3"

        result["genes_parsed"] = len(genes)
        chromosomes = sorted({g["chromosome"] for g in genes if g.get("chromosome")})
        print("    {} validated: {:,} gene models across {} sequences".format(
            fmt, len(genes), len(chromosomes)))

        # ── Enrich the Crop node with genome metadata ─────────────────────────
        # Resistance gene names (Sr33, Yr18, etc.) do NOT appear in NCBI/LIS
        # GFF3 annotation — those files use systematic locus IDs only.
        # We therefore store only genome-level statistics on the Crop node.
        enrich_query = """
        MERGE (c:Crop {name: $crop})
        SET c.genome_gene_count    = $gene_count,
            c.genome_seq_count     = $seq_count,
            c.genome_source        = $source,
            c.genome_indexed_at    = datetime()
        RETURN c.name AS name
        """
        driver = DBDriver()
        driver.connect()
        try:
            driver.run(
                enrich_query,
                crop=dataset["crop"],
                gene_count=len(genes),
                seq_count=len(chromosomes),
                source=dataset.get("source", ""),
            )
            print("    Crop node '{}' enriched with genome stats".format(dataset["crop"]))
        finally:
            driver.close()

        return result
    except Exception as exc:
        result["error"] = str(exc)
        return result


def run_pipeline() -> dict:
    """Execute the full data curation pipeline."""
    print("\n" + "=" * 60)
    print("[Pipeline] Starting data curation pipeline")
    print("=" * 60)

    print("\n[Registry] Loading from {}".format(DATASETS_PATH))
    registry = load_dataset_registry()
    print("[Registry] Loaded {} datasets".format(len(registry["datasets"])))

    downloaded_datasets = select_downloaded_datasets(registry)
    print("[Registry] Found {} downloaded datasets".format(len(downloaded_datasets)))

    if not downloaded_datasets:
        print("\n[Pipeline] Nothing to process -- no datasets have status: downloaded")
        return {"total_datasets": 0, "processed": 0, "genes_parsed": 0,
                "resistance_genes": 0, "genes_loaded": 0, "errors": []}

    print("\n[Database] Ensuring constraints...")
    driver = DBDriver()
    driver.connect()
    create_constraints(driver)
    driver.close()

    print("\n[Processing] Starting dataset processing...")
    summary = {
        "total_datasets": len(downloaded_datasets),
        "processed": 0,
        "genes_parsed": 0,
        "resistance_genes": 0,
        "genes_loaded": 0,
        "errors": [],
    }

    for dataset in downloaded_datasets:
        print("\n  [{}] crop={}".format(dataset["id"], dataset["crop"]))
        result = process_dataset(dataset)

        if result["error"]:
            print("    ERROR: {}".format(result["error"]))
            summary["errors"].append("{}: {}".format(dataset["id"], result["error"]))
            try:
                update_dataset_status(dataset["id"], "error")
                print("    Status -> error (recorded in datasets.yaml)")
            except Exception as status_exc:
                print("    WARNING: Could not update status: {}".format(status_exc))
        else:
            msg = "Parsed {:,} genes".format(result["genes_parsed"])
            if result["resistance_genes"] > 0:
                msg += ", {} resistance gene candidates".format(result["resistance_genes"])
            print("    {}".format(msg))
            print("    Loaded {:,} gene nodes into Neo4j".format(result["genes_loaded"]))
            summary["processed"] += 1
            summary["genes_parsed"] += result["genes_parsed"]
            summary["resistance_genes"] += result["resistance_genes"]
            summary["genes_loaded"] += result["genes_loaded"]
            try:
                update_dataset_status(dataset["id"], "loaded")
                print("    Status -> loaded (recorded in datasets.yaml)")
            except Exception as status_exc:
                print("    WARNING: Could not update status: {}".format(status_exc))

    print("\n" + "=" * 60)
    print("[Summary]")
    print("=" * 60)
    print("Datasets processed:     {}/{}".format(summary["processed"], summary["total_datasets"]))
    print("Genes parsed:           {:,}".format(summary["genes_parsed"]))
    print("Resistance candidates:  {:,}".format(summary["resistance_genes"]))
    print("Gene nodes in Neo4j:    {:,}".format(summary["genes_loaded"]))
    if summary["errors"]:
        print("\nErrors ({}):".format(len(summary["errors"])))
        for error in summary["errors"]:
            print("  - {}".format(error))
    print()
    return summary


def main() -> int:
    try:
        run_pipeline()
        return 0
    except Exception as exc:
        print("\nPipeline error: {}".format(exc), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
