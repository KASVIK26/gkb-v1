"""Controlled vocabularies for the KG v2 model (RESEARCH_ROADMAP.md §4)."""

from __future__ import annotations

from enum import StrEnum


class Crop(StrEnum):
    WHEAT = "wheat"
    SOYBEAN = "soybean"
    CHICKPEA = "chickpea"


class EntityType(StrEnum):
    CROP = "Crop"
    VARIETY = "Variety"
    GENE = "Gene"
    QTL = "QTL"
    MARKER = "Marker"
    REF_GENE = "RefGene"
    DISEASE = "Disease"
    PATHOGEN = "Pathogen"
    PATHOTYPE = "Pathotype"
    ENV_TRIGGER = "EnvTrigger"
    AGRO_ZONE = "AgroZone"
    ADVISORY = "Advisory"


# ID prefix per entity type, and whether the second ID segment must be a crop.
ID_PREFIX: dict[EntityType, str] = {
    EntityType.CROP: "crop",
    EntityType.VARIETY: "var",
    EntityType.GENE: "gene",
    EntityType.QTL: "qtl",
    EntityType.MARKER: "mk",
    EntityType.REF_GENE: "ref",
    EntityType.DISEASE: "dis",
    EntityType.PATHOGEN: "path",
    EntityType.PATHOTYPE: "pt",
    EntityType.ENV_TRIGGER: "env",
    EntityType.AGRO_ZONE: "zone",
    EntityType.ADVISORY: "adv",
}
CROP_SCOPED: frozenset[EntityType] = frozenset(
    {
        EntityType.VARIETY,
        EntityType.GENE,
        EntityType.QTL,
        EntityType.MARKER,
        EntityType.REF_GENE,
        EntityType.DISEASE,
        EntityType.ENV_TRIGGER,
        EntityType.AGRO_ZONE,
        EntityType.ADVISORY,
    }
)


class ClaimType(StrEnum):
    VARIETY_REACTION = "VARIETY_REACTION"
    VARIETY_CARRIES_GENE = "VARIETY_CARRIES_GENE"
    VARIETY_RECOMMENDED_FOR_ZONE = "VARIETY_RECOMMENDED_FOR_ZONE"
    VARIETY_DERIVED_FROM = "VARIETY_DERIVED_FROM"
    GENE_CONFERS_RESISTANCE = "GENE_CONFERS_RESISTANCE"
    GENE_PATHOTYPE_INTERACTION = "GENE_PATHOTYPE_INTERACTION"
    GENE_LOCATED_AT = "GENE_LOCATED_AT"
    QTL_ASSOCIATION = "QTL_ASSOCIATION"
    QTL_CONTAINS_REFGENE = "QTL_CONTAINS_REFGENE"
    MARKER_LINKAGE = "MARKER_LINKAGE"
    DISEASE_CAUSED_BY = "DISEASE_CAUSED_BY"
    PATHOTYPE_VARIANT_OF = "PATHOTYPE_VARIANT_OF"
    PATHOTYPE_PREVALENCE = "PATHOTYPE_PREVALENCE"
    DISEASE_ENV_TRIGGER = "DISEASE_ENV_TRIGGER"
    DISEASE_MANAGED_BY = "DISEASE_MANAGED_BY"


_E = EntityType
# Allowed (subject types, object types) per claim type.
CLAIM_SIGNATURE: dict[ClaimType, tuple[frozenset[EntityType], frozenset[EntityType]]] = {
    ClaimType.VARIETY_REACTION: (frozenset({_E.VARIETY}), frozenset({_E.DISEASE})),
    ClaimType.VARIETY_CARRIES_GENE: (frozenset({_E.VARIETY}), frozenset({_E.GENE})),
    ClaimType.VARIETY_RECOMMENDED_FOR_ZONE: (frozenset({_E.VARIETY}), frozenset({_E.AGRO_ZONE})),
    ClaimType.VARIETY_DERIVED_FROM: (frozenset({_E.VARIETY}), frozenset({_E.VARIETY})),
    ClaimType.GENE_CONFERS_RESISTANCE: (frozenset({_E.GENE}), frozenset({_E.DISEASE})),
    ClaimType.GENE_PATHOTYPE_INTERACTION: (frozenset({_E.GENE}), frozenset({_E.PATHOTYPE})),
    ClaimType.GENE_LOCATED_AT: (frozenset({_E.GENE}), frozenset({_E.REF_GENE})),
    ClaimType.QTL_ASSOCIATION: (frozenset({_E.QTL}), frozenset({_E.DISEASE})),
    ClaimType.QTL_CONTAINS_REFGENE: (frozenset({_E.QTL}), frozenset({_E.REF_GENE})),
    ClaimType.MARKER_LINKAGE: (frozenset({_E.MARKER}), frozenset({_E.GENE, _E.QTL})),
    ClaimType.DISEASE_CAUSED_BY: (frozenset({_E.DISEASE}), frozenset({_E.PATHOGEN})),
    ClaimType.PATHOTYPE_VARIANT_OF: (frozenset({_E.PATHOTYPE}), frozenset({_E.PATHOGEN})),
    ClaimType.PATHOTYPE_PREVALENCE: (frozenset({_E.PATHOTYPE}), frozenset({_E.AGRO_ZONE})),
    ClaimType.DISEASE_ENV_TRIGGER: (frozenset({_E.DISEASE}), frozenset({_E.ENV_TRIGGER})),
    ClaimType.DISEASE_MANAGED_BY: (frozenset({_E.DISEASE}), frozenset({_E.ADVISORY})),
}


class Reaction(StrEnum):
    """Host reaction class after scale harmonisation (Phase 7)."""

    R = "R"  # resistant
    MR = "MR"  # moderately resistant
    I = "I"  # intermediate  # noqa: E741
    MS = "MS"  # moderately susceptible
    S = "S"  # susceptible
    HS = "HS"  # highly susceptible


RESISTANT_REACTIONS = frozenset({Reaction.R, Reaction.MR})
SUSCEPTIBLE_REACTIONS = frozenset({Reaction.MS, Reaction.S, Reaction.HS})

# Susceptibility factor used by the risk engine (RESEARCH_ROADMAP.md §7.3).
SUSCEPTIBILITY: dict[Reaction, float] = {
    Reaction.R: 0.1,
    Reaction.MR: 0.35,
    Reaction.I: 0.5,
    Reaction.MS: 0.7,
    Reaction.S: 1.0,
    Reaction.HS: 1.0,
}
SUSCEPTIBILITY_UNKNOWN = 0.6


class PlantStage(StrEnum):
    SEEDLING = "seedling"
    ADULT = "adult"
    UNSPECIFIED = "unspecified"


class ResistanceType(StrEnum):
    ASR = "ASR"  # all-stage (seedling) resistance
    APR = "APR"  # adult-plant resistance
    QUANTITATIVE = "quantitative"
    UNKNOWN = "unknown"


class CarriesMethod(StrEnum):
    MARKER = "marker"
    SEQUENCE = "sequence"
    HAPLOTYPE = "haplotype"
    POSTULATION = "postulation"
    PEDIGREE = "pedigree"
    STATED = "stated"  # asserted by a source without method details


class ClaimStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    REVIEWED = "reviewed"
    PREDICTED = "predicted"  # model output (e.g. link prediction); never shown as fact
    REJECTED = "rejected"


class Tier(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class SourceType(StrEnum):
    PUBLICATION = "publication"  # id: pmid:<digits> or doi:<doi>
    DATASET = "dataset"  # id: ds:<slug>
    TRIAL_REPORT = "trial_report"  # id: trial:<slug>
    CATALOGUE = "catalogue"  # id: cat:<slug>
    OFFICIAL_DOCUMENT = "official_document"  # id: doc:<slug> (notifications, Package of Practices)
    CURATED_VOCAB = "curated_vocab"  # id: vocab:<file>
    TEST = "test"  # id: test:<slug>; rejected by release gates


SOURCE_ID_PREFIX: dict[SourceType, str] = {
    SourceType.PUBLICATION: "pmid|doi",
    SourceType.DATASET: "ds",
    SourceType.TRIAL_REPORT: "trial",
    SourceType.CATALOGUE: "cat",
    SourceType.OFFICIAL_DOCUMENT: "doc",
    SourceType.CURATED_VOCAB: "vocab",
    SourceType.TEST: "test",
}


class EvidenceMethod(StrEnum):
    """Kind of evidence behind a claim. Mapped to ECO terms in Phase 3 from the ECO
    ontology file itself (not hand-typed codes)."""

    CLONED_VALIDATED = "cloned_validated"
    DIAGNOSTIC_MARKER = "diagnostic_marker"
    LINKED_MARKER = "linked_marker"  # genotyped with a closely linked, non-diagnostic marker
    SEQUENCE_HAPLOTYPE = "sequence_haplotype"
    FIELD_MULTI_ENV = "field_multi_env"
    QTL_MAPPING = "qtl_mapping"
    GWAS = "gwas"
    FIELD_SINGLE_ENV = "field_single_env"
    CONTROLLED_ENV = "controlled_env"
    POSTULATION_PEDIGREE = "postulation_pedigree"
    REVIEW_STATEMENT = "review_statement"
    OFFICIAL_DOCUMENT = "official_document"
    COMPUTATIONAL = "computational"
    CURATOR_ASSERTION = "curator_assertion"


# Heuristic weights (RESEARCH_ROADMAP.md §4.4). Tunable; report a sensitivity analysis.
EVIDENCE_WEIGHT: dict[EvidenceMethod, float] = {
    EvidenceMethod.CLONED_VALIDATED: 1.00,
    EvidenceMethod.OFFICIAL_DOCUMENT: 0.90,
    EvidenceMethod.DIAGNOSTIC_MARKER: 0.85,
    EvidenceMethod.LINKED_MARKER: 0.65,
    EvidenceMethod.SEQUENCE_HAPLOTYPE: 0.85,
    EvidenceMethod.FIELD_MULTI_ENV: 0.80,
    EvidenceMethod.QTL_MAPPING: 0.70,
    EvidenceMethod.GWAS: 0.60,
    EvidenceMethod.COMPUTATIONAL: 0.60,
    EvidenceMethod.FIELD_SINGLE_ENV: 0.50,
    EvidenceMethod.CONTROLLED_ENV: 0.50,
    EvidenceMethod.CURATOR_ASSERTION: 0.50,
    EvidenceMethod.POSTULATION_PEDIGREE: 0.45,
    EvidenceMethod.REVIEW_STATEMENT: 0.35,
}
