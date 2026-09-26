"""Human-approval CLI for AI-extracted resistance records.

Reads records from ``data/review_queue.json`` (written by paper_extractor.py),
presents each one interactively, and lets the curator approve, skip, or edit
before records are moved to ``data/approved_queue.json`` for loading into Neo4j.

Usage
-----
::

    python curator/approve_extractions.py
    python curator/approve_extractions.py --queue data/review_queue.json
    python curator/approve_extractions.py --load   # also loads approved records into Neo4j

Workflow
--------
1. Run extraction:   ``python curator/extractors/paper_extractor.py paper.txt``
2. Review & approve: ``python curator/approve_extractions.py``
3. Load approved:    ``python curator/approve_extractions.py --load``
   (or run step 3 separately once you are satisfied with the approved queue)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW_QUEUE = ROOT_DIR / "data" / "review_queue.json"
DEFAULT_APPROVED_QUEUE = ROOT_DIR / "data" / "approved_queue.json"


# ---------------------------------------------------------------------------
# Queue I/O helpers
# ---------------------------------------------------------------------------

def load_queue(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR: Could not parse queue at {path}: {exc}") from exc


def save_queue(entries: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _fmt(value: object) -> str:
    if value is None:
        return "(none)"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "(none)"
    return str(value)


def display_record(index: int, total: int, entry: dict) -> None:
    rec = entry.get("record", {})
    source_file = entry.get("source_file", "unknown")
    print(f"\n{'─' * 60}")
    print(f"  Record {index + 1}/{total}   source: {source_file}")
    print(f"{'─' * 60}")
    print(f"  Gene:            {_fmt(rec.get('gene'))}")
    print(f"  Disease:         {_fmt(rec.get('disease'))}")
    print(f"  Pathogen:        {_fmt(rec.get('pathogen'))}")
    print(f"  Resistance type: {_fmt(rec.get('resistance_type'))}")
    print(f"  Varieties:       {_fmt(rec.get('varieties'))}")
    print(f"  Confidence:      {_fmt(rec.get('confidence'))}")
    print(f"  IoT trigger:     {_fmt(rec.get('iot_trigger'))}")
    print(f"  Treatment:       {_fmt(rec.get('treatment'))}")
    print(f"  Source citation: {_fmt(rec.get('source'))}")


# ---------------------------------------------------------------------------
# Interactive approval loop
# ---------------------------------------------------------------------------

_PROMPT = "\n  [a] Approve   [s] Skip   [e] Edit field   [q] Quit > "
CONFIDENCE_VALUES = ("Very High", "High", "Medium")


def _edit_field(rec: dict) -> dict:
    """Let the curator edit a single field of the record in-place."""
    editable = list(rec.keys())
    print("\n  Fields:")
    for i, field in enumerate(editable):
        print(f"    {i + 1}. {field}: {_fmt(rec[field])}")
    try:
        choice = int(input("  Field number to edit > ").strip())
        if not 1 <= choice <= len(editable):
            print("  Invalid choice.")
            return rec
        field = editable[choice - 1]
        current = rec[field]
        if isinstance(current, list):
            raw = input(f"  New value for {field!r} (comma-separated) > ").strip()
            rec[field] = [v.strip() for v in raw.split(",") if v.strip()]
        else:
            raw = input(f"  New value for {field!r} > ").strip()
            rec[field] = raw if raw else None
    except (ValueError, EOFError):
        print("  Cancelled.")
    return rec


def run_approval_loop(
    review_queue_path: Path = DEFAULT_REVIEW_QUEUE,
    approved_queue_path: Path = DEFAULT_APPROVED_QUEUE,
) -> tuple[int, int]:
    """Present pending records for human review.

    Returns:
        (approved_count, skipped_count)
    """
    entries = load_queue(review_queue_path)
    pending = [e for e in entries if e.get("status") == "pending"]

    if not pending:
        print("No pending records in the review queue.")
        return 0, 0

    print(f"\n{'=' * 60}")
    print(f"  AgriHub-KB — Extraction Review")
    print(f"  {len(pending)} record(s) awaiting approval")
    print(f"{'=' * 60}")

    approved: list[dict] = load_queue(approved_queue_path)
    approved_count = 0
    skipped_count = 0

    for idx, entry in enumerate(entries):
        if entry.get("status") != "pending":
            continue

        display_record(approved_count + skipped_count, len(pending), entry)

        while True:
            try:
                action = input(_PROMPT).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n  Interrupted — saving progress.")
                break

            if action == "a":
                entry["status"] = "approved"
                approved.append({"status": "approved", "record": entry["record"]})
                approved_count += 1
                print("  ✓ Approved.")
                break
            elif action == "s":
                entry["status"] = "skipped"
                skipped_count += 1
                print("  Skipped.")
                break
            elif action == "e":
                entry["record"] = _edit_field(entry["record"])
                display_record(approved_count + skipped_count, len(pending), entry)
            elif action == "q":
                print("  Quitting — saving progress.")
                save_queue(entries, review_queue_path)
                save_queue(approved, approved_queue_path)
                print(f"\n  Approved so far: {approved_count}  |  Skipped: {skipped_count}")
                return approved_count, skipped_count
            else:
                print("  Unrecognised. Press [a], [s], [e], or [q].")

    save_queue(entries, review_queue_path)
    save_queue(approved, approved_queue_path)
    print(f"\n{'=' * 60}")
    print(f"  Done!  Approved: {approved_count}  |  Skipped: {skipped_count}")
    print(f"  Approved records saved to: {approved_queue_path}")
    if approved_count:
        print("  Run with --load to push approved records into Neo4j.")
    print(f"{'=' * 60}\n")
    return approved_count, skipped_count


# ---------------------------------------------------------------------------
# Neo4j loader for approved records
# ---------------------------------------------------------------------------

def load_approved_into_neo4j(approved_queue_path: Path = DEFAULT_APPROVED_QUEUE) -> int:
    """Load approved records from the approved queue into Neo4j via loader.py.

    Returns:
        Number of records loaded.
    """
    from curator.db import DBDriver
    from curator.loader import load_edge_record

    approved = [e for e in load_queue(approved_queue_path) if e.get("status") == "approved"]
    if not approved:
        print("No approved records to load.")
        return 0

    print(f"\n[Loader] Connecting to Neo4j …")
    driver = DBDriver()
    driver.connect()

    loaded = 0
    errors = 0
    try:
        for entry in approved:
            rec = entry.get("record", {})
            try:
                load_edge_record(driver, rec)
                entry["status"] = "loaded"
                loaded += 1
                print(f"  ✓ Loaded: {rec.get('gene')} → {rec.get('disease')}")
            except Exception as exc:
                entry["status"] = "load_error"
                entry["load_error"] = str(exc)
                errors += 1
                print(f"  ✗ Error loading {rec.get('gene')}: {exc}")
    finally:
        driver.close()
        save_queue(approved, approved_queue_path)

    print(f"\n[Loader] Loaded {loaded} record(s). Errors: {errors}.")
    return loaded


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review and approve AI-extracted resistance records before loading into Neo4j."
    )
    parser.add_argument(
        "--queue",
        default=str(DEFAULT_REVIEW_QUEUE),
        help=f"Path to review queue JSON (default: {DEFAULT_REVIEW_QUEUE})",
    )
    parser.add_argument(
        "--approved",
        default=str(DEFAULT_APPROVED_QUEUE),
        help=f"Path to approved queue JSON (default: {DEFAULT_APPROVED_QUEUE})",
    )
    parser.add_argument(
        "--load",
        action="store_true",
        help="After reviewing, also load approved records into Neo4j",
    )
    parser.add_argument(
        "--load-only",
        action="store_true",
        help="Skip the review loop and just load already-approved records",
    )
    args = parser.parse_args()

    review_path = Path(args.queue)
    approved_path = Path(args.approved)

    if args.load_only:
        load_approved_into_neo4j(approved_path)
        return

    approved_count, _ = run_approval_loop(review_path, approved_path)

    if args.load and approved_count:
        load_approved_into_neo4j(approved_path)


if __name__ == "__main__":
    main()
