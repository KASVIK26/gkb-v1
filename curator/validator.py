"""Validation helpers for curator pipeline records.

Three layers:
1. Field-level  -- validate_edge_record: required fields + confidence enum
2. Batch-level  -- validate_no_duplicate_edge: (gene, disease, source) dedup
3. Graph-level  -- check_orphan_nodes: Variety nodes with no CARRIES edges
4. Batch runner -- validate_batch: routes failures to review_queue.json (C3)
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from curator.schema import CONFIDENCE_VALUES

if TYPE_CHECKING:
    from curator.db import DBDriver

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW_QUEUE = ROOT_DIR / "data" / "review_queue.json"


class ValidationError(ValueError):
    """Raised when a curated record does not conform to the expected schema."""


# ---------------------------------------------------------------------------
# Field-level validation
# ---------------------------------------------------------------------------

def validate_confidence(confidence: str) -> None:
    if confidence not in CONFIDENCE_VALUES:
        raise ValidationError(
            "Invalid confidence '{}'. Expected one of: {}".format(
                confidence, ", ".join(CONFIDENCE_VALUES)
            )
        )


def validate_required_fields(record: dict, required_fields: Iterable) -> None:
    missing = [f for f in required_fields if f not in record or record[f] in (None, "")]
    if missing:
        raise ValidationError("Missing required fields: {}".format(", ".join(missing)))


def validate_edge_record(record: dict) -> None:
    """Full single-record validation: required fields + confidence enum."""
    validate_required_fields(record, ("gene", "disease", "confidence", "source"))
    validate_confidence(record["confidence"])


# ---------------------------------------------------------------------------
# Batch-level duplicate detection (C1)
# ---------------------------------------------------------------------------

def validate_no_duplicate_edge(record: dict, existing_edges: list) -> None:
    """Raise ValidationError if (gene, disease, source) already in existing_edges.

    Same-source duplicates are rejected. Different sources for the same
    gene/disease pair are allowed (independent literature observations).
    """
    gene = (record.get("gene") or "").strip()
    disease = (record.get("disease") or "").strip()
    source = (record.get("source") or "").strip()

    if not gene or not disease or not source:
        return  # let validate_required_fields handle missing fields

    for existing in existing_edges:
        if (
            (existing.get("gene") or "").strip() == gene
            and (existing.get("disease") or "").strip() == disease
            and (existing.get("source") or "").strip() == source
        ):
            raise ValidationError(
                "Duplicate edge: gene=\'{}\' -> disease=\'{}\' from source=\'{}\' "
                "already exists in this batch.".format(gene, disease, source)
            )


# ---------------------------------------------------------------------------
# Batch validation with graceful failure to review_queue.json (C3)
# ---------------------------------------------------------------------------

def validate_batch(records: list, review_queue_path: Path = DEFAULT_REVIEW_QUEUE) -> list:
    """Validate a batch; route failures to review queue instead of crashing.

    Returns only the records that passed all checks.
    """
    valid: list = []
    accepted: list = []

    for record in records:
        errors: list = []

        try:
            validate_edge_record(record)
        except ValidationError as exc:
            errors.append(str(exc))

        if not errors:
            try:
                validate_no_duplicate_edge(record, accepted)
            except ValidationError as exc:
                errors.append(str(exc))

        if errors:
            msg = "; ".join(errors)
            logger.warning("Validation failed for %r: %s", record.get("gene"), msg)
            _append_to_review_queue(record, msg, review_queue_path)
        else:
            valid.append(record)
            accepted.append(record)

    return valid


def _append_to_review_queue(record: dict, error_message: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = []
    existing.append({"status": "pending", "error": error_message, "record": record})
    try:
        path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        logger.error("Could not write review queue at %s: %s", path, exc)


# ---------------------------------------------------------------------------
# Graph-level orphan node detection (C2)
# ---------------------------------------------------------------------------

def check_orphan_nodes(driver: "DBDriver") -> list:
    """Return Variety nodes with no outgoing CARRIES edges (likely data errors).

    Logs a warning for each orphan but does not raise.
    """
    query = """
    MATCH (v:Variety)
    WHERE NOT (v)-[:CARRIES]->(:Gene)
    RETURN v.name AS name
    ORDER BY name
    """
    orphans: list = []
    try:
        with driver.session() as session:
            result = session.run(query)
            orphans = [row["name"] for row in result if row["name"]]
    except Exception as exc:
        logger.error("Could not run orphan node check: %s", exc)
        return []

    if orphans:
        logger.warning(
            "%d orphan Variety node(s) found (no CARRIES edges): %s",
            len(orphans),
            ", ".join(orphans),
        )
    else:
        logger.info("No orphan Variety nodes detected.")

    return orphans
