"""A KG bundle (entities, sources, claims, evidence) and its release gates."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from curator.model import Claim, ClaimStatus, Entity, Evidence, Source, SourceType


@dataclass
class KGBundle:
    entities: list[Entity] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)

    @staticmethod
    def merge(*bundles: "KGBundle") -> "KGBundle":
        """Combine bundles from several sources (vocab-derived + hand-curated files).

        Entities are de-duplicated by ID (last bundle wins) — e.g. a Disease entity
        materialised once from config/vocab/ can be referenced by many curated files
        without each of them redefining it. A claim's id is derived from its content, so the
        same claim appearing in two files is ONE claim: the first copy is kept and the evidence
        from both files accumulates on it (that is how a second independent source is added to
        a claim that already exists). Evidence is concatenated as-is; gate_errors() catches a
        duplicated evidence id.
        """
        entities: dict[str, Entity] = {}
        sources: list[Source] = []
        claims: list[Claim] = []
        evidence: list[Evidence] = []
        seen_claims: set[str] = set()
        for b in bundles:
            entities.update({e.id: e for e in b.entities})
            sources.extend(b.sources)
            for claim in b.claims:
                if claim.id not in seen_claims:
                    seen_claims.add(claim.id)
                    claims.append(claim)
            evidence.extend(b.evidence)
        return KGBundle(entities=list(entities.values()), sources=sources, claims=claims, evidence=evidence)

    def gate_errors(self, *, allow_test_sources: bool = False) -> list[str]:
        """Checks that must pass before a bundle becomes a release. Empty list = OK."""
        errors: list[str] = []
        entity_ids = {e.id for e in self.entities}
        source_by_id = {s.id: s for s in self.sources}
        claim_ids = {c.id for c in self.claims}

        for name, ids in (
            ("entity", [e.id for e in self.entities]),
            ("source", [s.id for s in self.sources]),
            ("claim", [c.id for c in self.claims]),
            ("evidence", [e.id for e in self.evidence]),
        ):
            dupes = [i for i, n in Counter(ids).items() if n > 1]
            if dupes:
                errors.append(f"duplicate {name} IDs: {sorted(dupes)}")

        for claim in self.claims:
            for role, ref in (("subject", claim.subject_id), ("object", claim.object_id)):
                if ref not in entity_ids:
                    errors.append(f"{claim.id}: {role} {ref} is not a known entity")

        supported = {ev.claim_id for ev in self.evidence}
        for claim in self.claims:
            if claim.status is not ClaimStatus.REJECTED and claim.id not in supported:
                errors.append(f"{claim.id} ({claim.type.value}) has no evidence")

        for ev in self.evidence:
            if ev.claim_id not in claim_ids:
                errors.append(f"{ev.id}: evidence for unknown claim {ev.claim_id}")
            source = source_by_id.get(ev.source_id)
            if source is None:
                errors.append(f"{ev.id}: unknown source {ev.source_id}")
            elif source.type is SourceType.TEST and not allow_test_sources:
                errors.append(f"{ev.id}: test source {source.id} is not allowed in a release")
            elif source.type is SourceType.PUBLICATION and not source.verified:
                errors.append(f"{ev.id}: publication {source.id} metadata is not verified")
        return errors
