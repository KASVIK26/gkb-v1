"""Computed confidence for every claim (RESEARCH_ROADMAP.md §4.4) -- replaces hand-typed labels.

score = 1 - prod(1 - w_s) over INDEPENDENT sources s, where w_s is the strongest evidence weight that
source gives the claim after modifiers. Several evidence rows from one paper count once: a paper
repeating itself is not corroboration. The weights are a documented, tunable heuristic
(curator.model.enums.EVIDENCE_WEIGHT), not a measured probability.

Modifiers: x0.6 for LLM-extracted evidence no human has reviewed; x0.8 for evidence that is more than
10 years old when the claim depends on the pathogen's race/pathotype (pathotype populations drift, and
resistance that was real at release can be gone: a rust-resistant 2004 variety may be susceptible today).
That covers pathotype claims, any claim carrying a pathotype, and variety reactions to the race-structured
diseases in RACE_STRUCTURED_DISEASES. For a notification (official document) the age is the variety's RELEASE
year, not the year of the PDF that lists it; for anything else it is the source's year.
Conflict (the `conflict` flag, capped at tier C): a variety reported both resistant (R, MR) and susceptible
(MS, S, HS) to the same disease where the contexts are COMPATIBLE: stage and pathotype equal, or either one
unspecified. Place and season may differ -- that is exactly the "resistant in 2004, susceptible in 2021" case.
Seedling-susceptible with adult-resistant (the signature of adult-plant resistance) and R against one
pathotype with S against another are NOT conflicts. This is the same rule as competency query CQ10.
Tiers: A >= 0.85, B >= 0.65, C >= 0.40, D below.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from curator.graph.bundle import KGBundle
from curator.model import Claim, ClaimStatus, ClaimType, Evidence, Source
from curator.model.enums import EVIDENCE_WEIGHT, RESISTANT_REACTIONS, SUSCEPTIBLE_REACTIONS, Reaction, Tier

LLM_UNREVIEWED_FACTOR = 0.6
STALE_PATHOTYPE_FACTOR = 0.8
STALE_PATHOTYPE_YEARS = 10
TIER_THRESHOLDS = ((Tier.A, 0.85), (Tier.B, 0.65), (Tier.C, 0.40))
_PATHOTYPE_CLAIMS = frozenset({ClaimType.GENE_PATHOTYPE_INTERACTION, ClaimType.PATHOTYPE_PREVALENCE})
# Diseases whose pathogen is structured into races/pathotypes, so a variety's resistance is only as durable as the
# pathogen population it was tested against. (Slugs of the dis:<crop>:<slug> ids in config/vocab/diseases.yaml.)
RACE_STRUCTURED_DISEASES = frozenset(
    {"stripe_rust", "leaf_rust", "stem_rust", "rust", "powdery_mildew", "fusarium_wilt"}
)


def tier_for(score: float, *, conflict: bool = False) -> Tier:
    tier = next((t for t, floor in TIER_THRESHOLDS if score >= floor), Tier.D)
    if conflict and tier in (Tier.A, Tier.B):
        return Tier.C
    return tier


def _pathotype_dependent(claim: Claim) -> bool:
    if claim.type in _PATHOTYPE_CLAIMS or claim.qualifiers.get("pathotype_id"):
        return True
    return claim.type is ClaimType.VARIETY_REACTION and claim.object_id.rsplit(":", 1)[-1] in RACE_STRUCTURED_DISEASES


def _observation_year(evidence: Evidence, claim: Claim, source: Source | None, release_years: dict[str, int]) -> int | None:
    """When the thing reported was observed. A notification states the resistance a variety had when it was
    released; the PDF listing it may be decades newer."""
    if evidence.method.value == "official_document" and claim.type is ClaimType.VARIETY_REACTION:
        released = release_years.get(claim.subject_id)
        if released:
            return released
    return source.year if source is not None else None


def evidence_weight(
    evidence: Evidence, claim: Claim, source: Source | None, *, as_of_year: int, release_years: dict[str, int] | None = None
) -> float:
    weight = EVIDENCE_WEIGHT[evidence.method]
    if evidence.extractor.startswith("llm:") and evidence.reviewer is None:
        weight *= LLM_UNREVIEWED_FACTOR
    observed = _observation_year(evidence, claim, source, release_years or {})
    if _pathotype_dependent(claim) and observed is not None and as_of_year - observed > STALE_PATHOTYPE_YEARS:
        weight *= STALE_PATHOTYPE_FACTOR
    return weight


def claim_score(
    claim: Claim, evidence: list[Evidence], sources: dict[str, Source], *, as_of_year: int, release_years: dict[str, int] | None = None
) -> float:
    """Aggregate over independent sources; a source contributes its strongest evidence only."""
    best: dict[str, float] = {}
    for ev in evidence:
        w = evidence_weight(ev, claim, sources.get(ev.source_id), as_of_year=as_of_year, release_years=release_years)
        best[ev.source_id] = max(best.get(ev.source_id, 0.0), w)
    remaining = 1.0
    for w in best.values():
        remaining *= 1.0 - w
    return round(1.0 - remaining, 4)


def _compatible(a: Claim, b: Claim) -> bool:
    """Could both reports be about the same plants in the same biological situation? Stage and pathotype must not
    be known to differ; a report that does not state them could be about either."""
    def same_or_unknown(x: str | None, y: str | None, unknown: tuple) -> bool:
        return x in unknown or y in unknown or x == y

    qa, qb = a.qualifiers, b.qualifiers
    return same_or_unknown(qa.get("stage"), qb.get("stage"), (None, "unspecified")) and same_or_unknown(
        qa.get("pathotype_id"), qb.get("pathotype_id"), (None,)
    )


def conflicted_claim_ids(claims: list[Claim]) -> set[str]:
    """Reaction claims that disagree (resistant vs susceptible) with another claim about the same variety and
    disease in a compatible context (see the module docstring)."""
    groups: dict[tuple, list[Claim]] = defaultdict(list)
    for claim in claims:
        if claim.type is ClaimType.VARIETY_REACTION and claim.status is not ClaimStatus.REJECTED:
            groups[(claim.subject_id, claim.object_id)].append(claim)
    conflicted: set[str] = set()
    for members in groups.values():
        resistant = [c for c in members if Reaction(c.qualifiers["reaction"]) in RESISTANT_REACTIONS]
        susceptible = [c for c in members if Reaction(c.qualifiers["reaction"]) in SUSCEPTIBLE_REACTIONS]
        for r in resistant:
            for s in susceptible:
                if _compatible(r, s):
                    conflicted.update((r.id, s.id))
    return conflicted


def score_bundle(bundle: KGBundle, *, as_of_year: int | None = None) -> KGBundle:
    """Return a copy of `bundle` whose claims carry score, tier and conflict. Claim IDs are content
    hashes of type/subject/object/qualifiers, so scoring never changes an ID."""
    year = as_of_year if as_of_year is not None else date.today().year
    sources = {s.id: s for s in bundle.sources}
    by_claim: dict[str, list[Evidence]] = defaultdict(list)
    for ev in bundle.evidence:
        by_claim[ev.claim_id].append(ev)
    conflicts = conflicted_claim_ids(bundle.claims)
    release_years = {
        e.id: int(e.props["release_year"]) for e in bundle.entities if e.type.value == "Variety" and e.props.get("release_year")
    }

    scored: list[Claim] = []
    for claim in bundle.claims:
        evidence = by_claim.get(claim.id, [])
        if not evidence:
            scored.append(claim)
            continue
        score = claim_score(claim, evidence, sources, as_of_year=year, release_years=release_years)
        conflict = claim.id in conflicts
        scored.append(claim.model_copy(update={"score": score, "tier": tier_for(score, conflict=conflict), "conflict": conflict}))
    return KGBundle(entities=bundle.entities, sources=bundle.sources, claims=scored, evidence=bundle.evidence)


def summarize(bundle: KGBundle) -> dict:
    """Tier mix, corroboration and conflicts -- what a credibility report needs at a glance."""
    sources_per_claim: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()
    for ev in bundle.evidence:
        if (ev.claim_id, ev.source_id) not in seen:
            seen.add((ev.claim_id, ev.source_id))
            sources_per_claim[ev.claim_id] += 1
    scored = [c for c in bundle.claims if c.tier is not None]
    return {
        "claims": len(bundle.claims),
        "scored": len(scored),
        "tiers": dict(sorted(Counter(c.tier.value for c in scored).items())),
        "conflicts": sum(1 for c in bundle.claims if c.conflict),
        "single_source_claims": sum(1 for c in bundle.claims if sources_per_claim[c.id] == 1),
        "multi_source_claims": sum(1 for c in bundle.claims if sources_per_claim[c.id] >= 2),
    }
