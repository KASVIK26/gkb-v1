"""Canonical node and relationship schema for the AgriHub knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass


CONFIDENCE_VALUES = ("Very High", "High", "Medium")

NODE_LABELS = {
    "crop": "Crop",
    "variety": "Variety",
    "gene": "Gene",
    "disease": "Disease",
    "treatment": "Treatment",
    "dataset": "Dataset",
}

RELATIONSHIP_TYPES = {
    "variety_belongs_to_crop": "BELONGS_TO",
    "variety_carries_gene": "CARRIES",
    "gene_confers_resistance_to_disease": "CONFERS_RESISTANCE_TO",
    "disease_treated_by_treatment": "TREATED_BY",
    "gene_sourced_from_dataset": "SOURCED_FROM",
}


@dataclass(frozen=True)
class SchemaField:
    label: str
    properties: tuple[str, ...]


NODE_SCHEMAS = {
    "Crop": SchemaField(label="Crop", properties=("name",)),
    "Variety": SchemaField(label="Variety", properties=("name", "crop")),
    "Gene": SchemaField(label="Gene", properties=("id", "chromosome", "allele", "resistance_type")),
    "Disease": SchemaField(label="Disease", properties=("name", "pathogen")),
    "Treatment": SchemaField(label="Treatment", properties=("action", "iot_trigger")),
    "Dataset": SchemaField(label="Dataset", properties=("id", "source", "type")),
}
