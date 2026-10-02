"""Computed confidence for every claim (RESEARCH_ROADMAP.md §4.4) -- replaces hand-typed labels.

score = 1 - prod(1 - w_s) over INDEPENDENT sources s, where w_s is the strongest evidence weight that
source gives the claim after modifiers. Several evidence rows from one paper count once: a paper
repeating itself is not corroboration. The weights are a documented, tunable heuristic
(curator.model.enums.EVIDENCE_WEIGHT), not a measured probability.

Modifiers: x0.6 for LLM-extracted evidence no human has reviewed; x0.8 for pathotype-dependent
evidence from a source more than 10 years old (pathotype populations drift).
Conflict: a variety reported both resistant and susceptible to the same disease at the same stage,
pathotype, location and season. A conflicted claim is capped at tier C.
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


def tier_for(score: float, *, conflict: bool = False) -> Tier:
    tier = next((t for t, floor in TIER_THRESHOLDS if score >= floor), Tier.D)
    if conflict and tier in (Tier.A, Tier.B):
        return Tier.C
    return tier


def _pathotype_dependent(claim: Claim) -> bool:
    return claim.type in _PATHOTYPE_CLAIMS or bool(claim.qualifiers.get("pathotype_id"))


def evidence_weight(evidence: Evidence, claim: Claim, source: Source | None, *, as_of_year: int) -> float:
    weight = EVIDENCE_WEIGHT[evidence.method]
    if evidence.extractor.startswith("llm:") and evidence.reviewer is None:
        weight *= LLM_UNREVIEWED_FACTOR
    if (
        _pathotype_dependent(claim)
        and source is not None
        and source.year is not None
        and as_of_year - source.year > STALE_PATHOTYPE_YEARS
    ):
        weight *= STALE_PATHOTYPE_FACTOR
    return weight


def claim_score(claim: Claim, evidence: list[Evidence], sources: dict[str, Source], *, as_of_year: int) -> float:
    """Aggregate over independent sources; a source contributes its strongest evidence only."""
    best: dict[str, float] = {}
    for ev in evidence:
        w = evidence_weight(ev, claim, sources.get(ev.source_id), as_of_year=as_of_year)
        best[ev.source_id] = max(best.get(ev.source_id, 0.0), w)
    remaining = 1.0
    for w in best.values():
        remaining *= 1.0 - w
    return round(1.0 - remaining, 4)


def _reaction_context(claim: Claim) -> tuple:
    q = claim.qualifiers
    return (claim.subject_id, claim.object_id, q.get("stage"), q.get("pathotype_id"), q.get("location"), q.get("season"))


def conflicted_claim_ids(claims: list[Claim]) -> set[str]:
    """Claims that disagree (resistant vs susceptible) with another claim in the same context."""
    groups: dict[tuple, list[Claim]] = defaultdict(list)
    for claim in claims:
        if claim.type is ClaimType.VARIETY_REACTION and claim.status is not ClaimStatus.REJECTED:
            groups[_reaction_context(claim)].append(claim)
    conflicted: set[str] = set()
    for members in groups.values():
        reactions = {Reaction(c.qualifiers["reaction"]) for c in members}
        if reactions & RESISTANT_REACTIONS and reactions & SUSCEPTIBLE_REACTIONS:
            conflicted.update(c.id for c in members)
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

    scored: list[Claim] = []
    for claim in bundle.claims:
        evidence = by_claim.get(claim.id, [])
        if not evidence:
            scored.append(claim)
            continue
        score = claim_score(claim, evidence, sources, as_of_year=year)
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
