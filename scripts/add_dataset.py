"""CLI utility to register a new dataset in config/datasets.yaml.

Usage
-----
    python scripts/add_dataset.py

The script prompts for required metadata, then appends a new entry to
datasets.yaml with status: not_downloaded.  It validates that the given
id is not already taken and that the crop is one of the supported values.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[1]
DATASETS_PATH = ROOT_DIR / "config" / "datasets.yaml"

SUPPORTED_CROPS = ("wheat", "soybean", "chickpea")
SUPPORTED_TYPES = ("gene_annotation", "reference_assembly", "vcf")


def _prompt(prompt_text: str, default: str = "") -> str:
    """Prompt the user and return stripped input, falling back to default."""
    suffix = " [{}]: ".format(default) if default else ": "
    try:
        value = input(prompt_text + suffix).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        sys.exit(0)
    return value or default


def _choose(prompt_text: str, options: tuple) -> str:
    """Present a numbered menu and return the chosen option."""
    print("{}:".format(prompt_text))
    for i, opt in enumerate(options, 1):
        print("  {}. {}".format(i, opt))
    while True:
        raw = _prompt("Enter number", "1")
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass
        print("  Please enter a number between 1 and {}.".format(len(options)))


def load_registry(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        registry = yaml.safe_load(f) or {}
    registry.setdefault("datasets", [])
    return registry


def save_registry(registry: dict, path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(registry, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def main() -> None:
    print("\n" + "=" * 55)
    print("  AgriHub-KB -- Add New Dataset")
    print("=" * 55)
    print("This will append a new entry to config/datasets.yaml")
    print("with status: not_downloaded.\n")

    # Load existing registry to check for duplicate IDs
    registry = load_registry(DATASETS_PATH)
    existing_ids = {d.get("id") for d in registry.get("datasets", [])}

    # Collect metadata
    while True:
        dataset_id = _prompt("Dataset ID (e.g. wheat_iwgsc_gff3_v3)")
        if not dataset_id:
            print("  ID cannot be empty.")
            continue
        if dataset_id in existing_ids:
            print("  ID '{}' already exists in datasets.yaml. Choose a different ID.".format(dataset_id))
            continue
        break

    crop = _choose("Crop", SUPPORTED_CROPS)
    dataset_type = _choose("Dataset type", SUPPORTED_TYPES)
    local_path = _prompt("Local file path (relative to project root)",
                         "data/raw/{}.gff.gz".format(dataset_id))
    source = _prompt("Source / citation (e.g. IWGSC / URGI INRAE, PRJNA392179)")

    assembly_report = ""
    if dataset_type == "gene_annotation":
        ans = _prompt("Does this dataset have an NCBI assembly report? [y/N]", "n").lower()
        if ans in ("y", "yes"):
            assembly_report = _prompt(
                "Assembly report path",
                "data/raw/{}_assembly_report.txt".format(dataset_id)
            )

    # Build entry
    entry: dict = {
        "id": dataset_id,
        "crop": crop,
        "type": dataset_type,
        "local_path": local_path,
        "source": source,
        "status": "not_downloaded",
    }
    if assembly_report:
        entry["assembly_report"] = assembly_report

    # Preview
    print("\n  Entry to be added:")
    print("  " + "-" * 40)
    for k, v in entry.items():
        print("  {}: {}".format(k, v))
    print("  " + "-" * 40)

    confirm = _prompt("\nAdd this entry to datasets.yaml? [Y/n]", "y").lower()
    if confirm not in ("y", "yes", ""):
        print("Aborted -- nothing written.")
        return

    registry["datasets"].append(entry)
    save_registry(registry, DATASETS_PATH)

    print("\nAdded '{}' to {} with status: not_downloaded".format(dataset_id, DATASETS_PATH))
    print("Next steps:")
    print("  1. Download the file to: {}".format(local_path))
    print("  2. Update status to \'downloaded\' in datasets.yaml")
    print("  3. Run: python curator/run_pipeline.py")


if __name__ == "__main__":
    main()
