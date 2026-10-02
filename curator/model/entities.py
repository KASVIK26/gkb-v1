"""Entity (node) models. Every entity has a namespaced ID and typed properties."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from curator.model.enums import Crop, EntityType
from curator.normalize.ids import parse_id, validate_chromosome

VOCAB_DIR = Path(__file__).resolve().parents[2] / "config" / "vocab"


class _Props(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CropProps(_Props):
    species: str | None = None


class VarietyProps(_Props):
    release_year: int | None = Field(default=None, ge=1900, le=2100)
    releasing_institute: str | None = None
    notification: str | None = None  # gazette notification number / S.O. reference
    market_type: str | None = None  # desi | kabuli | bread | durum | ...
    maturity_days: tuple[int, int] | None = None  # (min, max)
    pedigree: str | None = None
    accession_ids: list[str] = []  # IC / PI / ICC / EC numbers
    is_check: bool = False  # standard susceptible/resistant check in trials


class GeneProps(_Props):
    symbol: str
    chromosome: str | None = None
    origin_species: str | None = None  # e.g. alien donor species
    gene_class: str | None = None  # NLR, ABC transporter, kinase, ...
    cloned: bool | None = None


class QTLProps(_Props):
    trait: str
    chromosome: str | None = None
    population: str | None = None


class MarkerProps(_Props):
    marker_type: Literal["KASP", "SSR", "STS", "SNP", "CAPS", "SCAR", "other"]
    chromosome: str | None = None
    sequence: str | None = None  # primer/probe for anchoring on the reference


class RefGeneProps(_Props):
    locus_id: str
    assembly: str
    chromosome: str
    start_bp: int = Field(ge=1)
    end_bp: int = Field(ge=1)
    strand: Literal["+", "-", "."]
    description: str | None = None
    domains: list[str] = []
    is_nlr: bool = False
    nlr_class: Literal["CNL", "TNL", "RNL", "NL", "RLK", "RLP"] | None = None

    @model_validator(mode="after")
    def _ordered(self) -> RefGeneProps:
        if self.end_bp < self.start_bp:
            raise ValueError("end_bp must be >= start_bp")
        return self


class DiseaseProps(_Props):
    group: str | None = None  # e.g. dis:wheat:rusts


class PathogenProps(_Props):
    ncbi_taxon: int | None = None  # resolved by lookup in Phase 3, never hand-typed
    pathogen_type: str | None = None


class PathotypeProps(_Props):
    designation: str
    virulence_formula: str | None = None
    first_reported_year: int | None = Field(default=None, ge=1900, le=2100)


class TriggerCondition(_Props):
    variable: str
    min: float | None = None
    max: float | None = None
    aggregation: Literal["mean", "min", "max", "sum", "count"]
    window_h: int = Field(gt=0, le=24 * 30)

    @field_validator("variable")
    @classmethod
    def _known_variable(cls, value: str) -> str:
        if value not in sensor_variable_names():
            raise ValueError(f"{value!r} is not a variable in config/vocab/sensors.yaml")
        return value

    @model_validator(mode="after")
    def _has_bound(self) -> TriggerCondition:
        if self.min is None and self.max is None:
            raise ValueError("a trigger condition needs min and/or max")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min must be <= max")
        return self


class EnvTriggerProps(_Props):
    phase: Literal["infection", "sporulation", "spread", "survival", "expression"]
    conditions: list[TriggerCondition] = Field(min_length=1)
    bbch_from: int = Field(ge=0, le=99)
    bbch_to: int = Field(ge=0, le=99)

    @model_validator(mode="after")
    def _window(self) -> EnvTriggerProps:
        if self.bbch_from > self.bbch_to:
            raise ValueError("bbch_from must be <= bbch_to")
        return self


class AgroZoneProps(_Props):
    system: Literal["AICRP", "agroclimatic", "state", "district"]
    states: list[str] = []


class AdvisoryProps(_Props):
    """What to do, structured enough to act on. Everything but action_type is optional and is recorded
    as the source states it -- never inferred or converted -- so an advisory without a dose says so
    rather than guessing one."""

    action_type: Literal["cultural", "biological", "chemical", "varietal", "monitoring"]
    active_ingredient: str | None = None  # product / active ingredient and formulation, as published
    dose: str | None = None  # rate with its unit, as published (e.g. "1 mL/L", "0.1%")
    timing: str | None = None  # when to act, in the source's words
    bbch_from: int | None = Field(default=None, ge=0, le=99)
    bbch_to: int | None = Field(default=None, ge=0, le=99)
    region: str | None = None  # where the source says this applies (trial site or issuing zone): local relevance varies

    @model_validator(mode="after")
    def _stage_window(self) -> AdvisoryProps:
        if (self.bbch_from is None) != (self.bbch_to is None):
            raise ValueError("set bbch_from and bbch_to together, or neither")
        if self.bbch_from is not None and self.bbch_from > self.bbch_to:
            raise ValueError("bbch_from must be <= bbch_to")
        return self


PROPS_MODEL: dict[EntityType, type[_Props]] = {
    EntityType.CROP: CropProps,
    EntityType.VARIETY: VarietyProps,
    EntityType.GENE: GeneProps,
    EntityType.QTL: QTLProps,
    EntityType.MARKER: MarkerProps,
    EntityType.REF_GENE: RefGeneProps,
    EntityType.DISEASE: DiseaseProps,
    EntityType.PATHOGEN: PathogenProps,
    EntityType.PATHOTYPE: PathotypeProps,
    EntityType.ENV_TRIGGER: EnvTriggerProps,
    EntityType.AGRO_ZONE: AgroZoneProps,
    EntityType.ADVISORY: AdvisoryProps,
}

_CHROMOSOME_TYPES = {EntityType.GENE, EntityType.QTL, EntityType.MARKER}


class Entity(BaseModel):
    """A KG node. `props` is validated against the model for its type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    type: EntityType
    name: str = Field(min_length=1)
    crop: Crop | None = None
    synonyms: list[str] = []
    name_i18n: dict[str, str] = {}  # {"hi": "...", "mr": "..."}
    props: dict[str, Any] = {}

    @model_validator(mode="after")
    def _consistent(self) -> Entity:
        id_type, id_crop, _ = parse_id(self.id)
        if id_type is not self.type:
            raise ValueError(f"ID {self.id!r} is a {id_type.value}, not a {self.type.value}")
        if id_crop is not None and self.crop is not id_crop:
            raise ValueError(f"crop {self.crop} does not match ID {self.id!r}")

        props = PROPS_MODEL[self.type].model_validate(self.props)
        chromosome = getattr(props, "chromosome", None)
        if chromosome is not None and self.type in _CHROMOSOME_TYPES:
            if self.crop is None:
                raise ValueError("an entity with a chromosome needs a crop")
            validate_chromosome(self.crop, chromosome)
        return self

    @property
    def typed_props(self) -> _Props:
        return PROPS_MODEL[self.type].model_validate(self.props)


@lru_cache(maxsize=1)
def sensor_variable_names() -> frozenset[str]:
    vocab = yaml.safe_load((VOCAB_DIR / "sensors.yaml").read_text(encoding="utf-8"))
    sections = ("measured", "fused", "derived", "external")
    return frozenset(v["name"] for section in sections for v in vocab[section])
