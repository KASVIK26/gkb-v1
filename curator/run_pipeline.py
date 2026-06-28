"""Orchestrate the full data pipeline: registry → parse → extract → load."""

from __future__ import annotations

from pathlib import Path

import yaml

from curator.db import DBDriver
from curator.init_constraints import create_constraints
from curator.parsers.gff_parser import parse_gff3, extract_resistance_genes
from curator.parsers.genomic_integration import load_chromosome_mappings
from curator.validator import ValidationError
from curator.load_genes import load_genes


ROOT_DIR = Path(__file__).resolve().parents[1]
DATASETS_PATH = ROOT_DIR / "config" / "datasets.yaml"


def load_dataset_registry(path: Path = DATASETS_PATH) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        registry = yaml.safe_load(handle) or {}

    if not isinstance(registry, dict):
        raise ValidationError("Dataset registry must be a mapping at the top level.")

    registry.setdefault("datasets", [])
    return registry


def select_downloaded_datasets(registry: dict) -> list[dict]:
    datasets = registry.get("datasets", [])
    if not isinstance(datasets, list):
        raise ValidationError("The 'datasets' key must contain a list.")

    return [dataset for dataset in datasets if dataset.get("status") == "downloaded"]


def process_dataset(dataset: dict) -> dict:
    """
    Process a single dataset: parse GFF3 and extract resistance genes.

    Args:
        dataset: Dataset entry from registry

    Returns:
        Processing result dict
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
        # Check if this is a GFF file (gzip compressed)
        local_path = dataset["local_path"]
        if not any(local_path.endswith(ext) for ext in [".gff.gz", ".gff3.gz", ".gbff.gz"]):
            result["error"] = "Not GFF3 format"
            return result
        
        gff3_path = Path(dataset["local_path"])
        if not gff3_path.exists():
            result["error"] = f"File not found: {gff3_path}"
            return result
        
        # Load chromosome mappings if assembly report available
        chromosome_mappings = None
        if "assembly_report" in dataset and dataset["assembly_report"]:
            report_path = Path(dataset["assembly_report"])
            if report_path.exists():
                chromosome_mappings = load_chromosome_mappings(report_path)
        
        # Parse GFF3
        genes = parse_gff3(gff3_path, chromosome_mappings)
        result["genes_parsed"] = len(genes)
        
        # Extract resistance genes (wheat/chickpea)
        if dataset["crop"] in ["wheat", "chickpea"]:
            resistance_genes = extract_resistance_genes(genes)
            result["resistance_genes"] = len(resistance_genes)
        
        # Load genes into Neo4j
        driver = DBDriver()
        driver.connect()
        try:
            result["genes_loaded"] = load_genes(driver, genes, dataset["crop"])
        finally:
            driver.close()
        
        return result
    
    except Exception as e:
        result["error"] = str(e)
        return result


def run_pipeline() -> dict:
    """
    Execute the full data curation pipeline.

    Steps:
    1. Load dataset registry
    2. Filter to downloaded datasets
    3. For each dataset: parse GFF3 → extract resistance genes
    4. Return summary statistics
    """
    print(f"\n{'='*60}")
    print("[Pipeline] Starting data curation pipeline")
    print('='*60)
    
    # Step 1: Load registry and filter
    print(f"\n[Registry] Loading from {DATASETS_PATH}")
    registry = load_dataset_registry()
    print(f"[Registry] Loaded {len(registry['datasets'])} datasets")
    
    downloaded_datasets = select_downloaded_datasets(registry)
    print(f"[Registry] Found {len(downloaded_datasets)} downloaded datasets")
    
    # Step 2: Ensure database constraints
    print("\n[Database] Ensuring constraints...")
    driver = DBDriver()
    driver.connect()
    create_constraints(driver)
    driver.close()
    
    # Step 3: Process each dataset
    print("\n[Processing] Starting dataset processing...")
    summary = {
        "total_datasets": len(downloaded_datasets),
        "processed": 0,
        "genes_parsed": 0,
        "resistance_genes": 0,
        "errors": [],
        "genes_loaded": 0,
    }
    
    for dataset in downloaded_datasets:
        print(f"\n  - {dataset['id']} ({dataset['crop']})")
        result = process_dataset(dataset)
        
        if result["error"]:
            print(f"    ERROR: {result['error']}")
            summary["errors"].append(f"{dataset['id']}: {result['error']}")
        else:
            print(f"    Parsed {result['genes_parsed']:,} genes", end="")
            if result["resistance_genes"] > 0:
                print(f", {result['resistance_genes']} resistance genes")
            else:
                print()
            summary["processed"] += 1
            summary["genes_parsed"] += result["genes_parsed"]
            summary["resistance_genes"] += result["resistance_genes"]
            summary["genes_loaded"] += result["genes_loaded"]
    
    # Summary
    print("\n" + "="*60)
    print("[Summary]")
    print("="*60)
    print(f"Datasets processed:    {summary['processed']}/{summary['total_datasets']}")
    print(f"Genes parsed:          {summary['genes_parsed']:,}")
    print(f"Resistance genes:      {summary['resistance_genes']:,}")
    print(f"Genes loaded in Neo4j:  {summary['genes_loaded']:,}")
    if summary["errors"]:
        print(f"\nErrors ({len(summary['errors'])}):")
        for error in summary["errors"]:
            print(f"  - {error}")
    print()
    
    return summary


def main() -> int:
    try:
        run_pipeline()
        return 0
    except Exception as e:
        print(f"\nPipeline error: {e}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
