"""Validation helpers for curator pipeline records."""

from __future__ import annotations

from collections.abc import Iterable

from curator.schema import CONFIDENCE_VALUES


class ValidationError(ValueError):
    """Raised when a curated record does not conform to the expected schema."""


def validate_confidence(confidence: str) -> None:
    if confidence not in CONFIDENCE_VALUES:
        raise ValidationError(f"Invalid confidence '{confidence}'. Expected one of {CONFIDENCE_VALUES}.")


def validate_required_fields(record: dict, required_fields: Iterable[str]) -> None:
    missing = [field for field in required_fields if field not in record or record[field] in (None, "")]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")


def validate_edge_record(record: dict) -> None:
    required_fields = ("gene", "disease", "confidence", "source")
    validate_required_fields(record, required_fields)
    validate_confidence(record["confidence"])
