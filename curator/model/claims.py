"""Claims (reified facts), evidence and sources (RESEARCH_ROADMAP.md §4.2–4.3).

Every fact in the KG is a Claim about (subject, object) with typed qualifiers.
Every Claim needs at least one Evidence row pointing to a Source.

Claim IDs are content hashes of (type, subject, object, qualifiers). The same fact
reported by two papers is one claim with two evidence rows. Observations with
different context (another location, season or pathotype) are separate claims,
and consensus across them is computed later (Phase 9).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from curator.model.enums import (
    CLAIM_SIGNATURE,
    SOURCE_ID_PREFIX,
    CarriesMethod,
    ClaimStatus,
    ClaimType,
    EvidenceMethod,
    PlantStage,
    Reaction,
    ResistanceType,
    SourceType,
    Tier,
)
from curator.normalize.ids import content_hash, parse_id


class _Q(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ─────────────────────────── qualifiers per claim type ───────────────────────────
class VarietyReactionQ(_Q):
    reaction: Reaction
    stage: PlantStage
    pathotype_id: str | None = None
    location: str | None = None
    season: str | None = None  # e.g. "2022-23" (rabi) or "2023" (kharif)
    n_locations: int | None = Field(default=None, ge=1)
    score_raw: str | None = None  # as published, e.g. "40S", "ACI 12.5", "7 (1-9)"
    scale: str | None = None


class VarietyCarriesGeneQ(_Q):
    method: CarriesMethod
    allele: str | None = None


class VarietyRecommendedForZoneQ(_Q):
    season: Literal["kharif", "rabi", "summer"] | None = None
    sowing: Literal["early", "timely", "late"] | None = None
    water_regime: Literal["irrigated", "rainfed", "restricted_irrigation"] | None = None


class VarietyDerivedFromQ(_Q):
    role: Literal["parent", "selection_from", "backcross_donor", "recurrent_parent"]


class GeneConfersResistanceQ(_Q):
    resistance_type: ResistanceType
    spectrum: str | None = None


class GenePathotypeInteractionQ(_Q):
    outcome: Literal["effective", "defeated"]
    year: int | None = Field(default=None, ge=1900, le=2100)
    region: str | None = None


class GeneLocatedAtQ(_Q):
    method: Literal["documented_locus", "blast", "diamond", "liftover"]
    assembly: str
    identity_pct: float | None = Field(default=None, ge=0, le=100)


class QtlAssociationQ(_Q):
    stage: PlantStage = PlantStage.UNSPECIFIED
    left_marker: str | None = None
    right_marker: str | None = None
    assembly: str | None = None
    start_bp: int | None = Field(default=None, ge=1)
    end_bp: int | None = Field(default=None, ge=1)
    lod: float | None = None
    p_value: float | None = Field(default=None, gt=0, le=1)
    pve_pct: float | None = Field(default=None, ge=0, le=100)
    population: str | None = None
    n_env: int | None = Field(default=None, ge=1)


class QtlContainsRefGeneQ(_Q):
    assembly: str
    rank: int | None = Field(default=None, ge=1)


class MarkerLinkageQ(_Q):
    distance_cm: float | None = Field(default=None, ge=0)
    diagnostic: bool = False


class EmptyQ(_Q):
    pass


class PathotypePrevalenceQ(_Q):
    years: list[int] = Field(min_length=1)
    frequency_pct: float | None = Field(default=None, ge=0, le=100)


QUALIFIERS: dict[ClaimType, type[_Q]] = {
    ClaimType.VARIETY_REACTION: VarietyReactionQ,
    ClaimType.VARIETY_CARRIES_GENE: VarietyCarriesGeneQ,
    ClaimType.VARIETY_RECOMMENDED_FOR_ZONE: VarietyRecommendedForZoneQ,
    ClaimType.VARIETY_DERIVED_FROM: VarietyDerivedFromQ,
    ClaimType.GENE_CONFERS_RESISTANCE: GeneConfersResistanceQ,
    ClaimType.GENE_PATHOTYPE_INTERACTION: GenePathotypeInteractionQ,
    ClaimType.GENE_LOCATED_AT: GeneLocatedAtQ,
    ClaimType.QTL_ASSOCIATION: QtlAssociationQ,
    ClaimType.QTL_CONTAINS_REFGENE: QtlContainsRefGeneQ,
    ClaimType.MARKER_LINKAGE: MarkerLinkageQ,
    ClaimType.DISEASE_CAUSED_BY: EmptyQ,
    ClaimType.PATHOTYPE_VARIANT_OF: EmptyQ,
    ClaimType.PATHOTYPE_PREVALENCE: PathotypePrevalenceQ,
    ClaimType.DISEASE_ENV_TRIGGER: EmptyQ,
    ClaimType.DISEASE_MANAGED_BY: EmptyQ,
}


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: ClaimType
    subject_id: str
    object_id: str
    qualifiers: dict[str, Any] = {}
    status: ClaimStatus = ClaimStatus.UNREVIEWED
    score: float | None = Field(default=None, ge=0, le=1)  # computed in Phase 9
    tier: Tier | None = None
    conflict: bool = False

    @model_validator(mode="before")
    @classmethod
    def _normalise_qualifiers(cls, data: Any) -> Any:
        if isinstance(data, dict) and "type" in data:
            model = QUALIFIERS[ClaimType(data["type"])]
            parsed = model.model_validate(data.get("qualifiers") or {})
            data = {**data, "qualifiers": parsed.model_dump(mode="json", exclude_none=True)}
        return data

    @model_validator(mode="after")
    def _signature(self) -> Claim:
        subject_types, object_types = CLAIM_SIGNATURE[self.type]
        subject_type = parse_id(self.subject_id)[0]
        object_type = parse_id(self.object_id)[0]
        if subject_type not in subject_types:
            raise ValueError(f"{self.type.value} subject must be {sorted(subject_types)}, got {subject_type.value}")
        if object_type not in object_types:
            raise ValueError(f"{self.type.value} object must be {sorted(object_types)}, got {object_type.value}")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def id(self) -> str:
        return content_hash(
            "claim",
            {"type": self.type.value, "s": self.subject_id, "o": self.object_id, "q": self.qualifiers},
        )


# ─────────────────────────── sources ───────────────────────────
_SOURCE_ID_RE = {
    stype: re.compile(rf"^(?:{prefixes}):\S+$") for stype, prefixes in SOURCE_ID_PREFIX.items()
}
_PMID_RE = re.compile(r"^pmid:\d+$")


class Source(BaseModel):
    """Where evidence comes from. `verified` = metadata checked against the registry
    (PubMed esummary / Crossref / issuing body), not typed from memory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    type: SourceType
    title: str = Field(min_length=1)
    year: int | None = Field(default=None, ge=1900, le=2100)
    venue: str | None = None  # journal, publisher or issuing institute
    url: str | None = None
    license: str | None = None
    verified: bool = False

    @model_validator(mode="after")
    def _id_matches_type(self) -> Source:
        if not _SOURCE_ID_RE[self.type].match(self.id):
            raise ValueError(f"source ID {self.id!r} does not fit type {self.type.value}")
        if self.id.startswith("pmid:") and not _PMID_RE.match(self.id):
            raise ValueError(f"PMID source IDs must be numeric: {self.id!r}")
        return self


# ─────────────────────────── evidence ───────────────────────────
_EXTRACTOR_RE = re.compile(r"^(?:llm|parser|pipeline|manual):\S+$")
MIN_QUOTE_CHARS = 20


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str
    source_id: str
    method: EvidenceMethod
    extractor: str  # llm:<model>@<prompt_v> | parser:<name>@<v> | pipeline:<name>@<v> | manual:<who>
    locator: str | None = None  # section / table / row / page
    quote: str | None = None
    reviewer: str | None = None
    reviewed_at: datetime | None = None

    @model_validator(mode="after")
    def _rules(self) -> Evidence:
        if not _EXTRACTOR_RE.match(self.extractor):
            raise ValueError(f"extractor {self.extractor!r} must look like 'llm:<model>@<prompt>'")
        if self.extractor.startswith("llm:") and len((self.quote or "").strip()) < MIN_QUOTE_CHARS:
            raise ValueError("LLM-extracted evidence needs a verbatim quote from the source")
        if (self.reviewer is None) != (self.reviewed_at is None):
            raise ValueError("reviewer and reviewed_at must be set together")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def id(self) -> str:
        return content_hash(
            "ev",
            {"c": self.claim_id, "s": self.source_id, "l": self.locator, "q": self.quote, "m": self.method.value},
        )
