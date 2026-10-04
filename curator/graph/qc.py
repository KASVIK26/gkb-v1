"""Quality-control report and sensitivity analysis for a KG bundle (RESEARCH_ROADMAP.md phase 9: "QC reports", "sensitivity analysis for the paper").

`qc_report` answers: how big is the graph, how well is every claim supported, where are the gaps (per crop and per disease), what is structurally wrong (orphan entities,
names that collide), and how far is it from the roadmap's targets. `sensitivity` re-scores the whole graph under alternative scoring parameters (the model-evidence discount,
the staleness factor, the evidence weights, the tier cut-offs) and reports how many claims change tier: the confidence tiers are only worth showing if they do not hinge on one
arbitrary constant. Both are pure functions of a bundle; `agrihub kg qc` renders them to Markdown.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass

import curator.model  # noqa: F401  (import order: curator.model before curator.normalize)
from curator.graph import scoring
from curator.graph.bundle import KGBundle
from curator.model.enums import EVIDENCE_WEIGHT, Tier
from curator.normalize.ids import lookup_key

TARGETS = {  # RESEARCH_ROADMAP.md section 10
    "varieties": {"wheat": 150, "soybean": 80, "chickpea": 80},
    "reaction_claims": 3000,
    "wheat_genes": 250,
    "soybean_loci": 60,
    "chickpea_qtls": 40,
}


def _crop(entity_id: str) -> str | None:
    parts = entity_id.split(":")
    return parts[1] if len(parts) > 2 and parts[1] in ("wheat", "soybean", "chickpea") else None


def qc_report(bundle: KGBundle) -> dict:
    entities = {e.id: e for e in bundle.entities}
    by_claim: dict[str, list] = defaultdict(list)
    for ev in bundle.evidence:
        by_claim[ev.claim_id].append(ev)
    claims = bundle.claims
    sources = {s.id: s for s in bundle.sources}

    def n_sources(claim_id: str) -> int:
        return len({ev.source_id for ev in by_claim[claim_id]})

    report: dict = {}
    report["entities"] = dict(sorted(Counter(e.type.value for e in bundle.entities).items()))
    report["claims_by_type"] = dict(Counter(c.type.value for c in claims).most_common())
    report["sources_by_type"] = dict(Counter(s.type.value for s in bundle.sources).items())
    report["evidence_by_method"] = dict(Counter(ev.method.value for ev in bundle.evidence).most_common())
    report["evidence_by_extractor"] = dict(Counter(ev.extractor.split("@")[0] for ev in bundle.evidence).most_common())

    # provenance integrity
    llm_only = sum(1 for c in claims if by_claim[c.id] and all(ev.extractor.startswith("llm:") for ev in by_claim[c.id]))
    report["provenance"] = {
        "claims": len(claims),
        "without_evidence": sum(1 for c in claims if not by_claim[c.id]),
        "with_only_model_found_evidence": llm_only,
        "with_one_source": sum(1 for c in claims if n_sources(c.id) == 1),
        "with_two_or_more_sources": sum(1 for c in claims if n_sources(c.id) >= 2),
        "human_reviewed_evidence": sum(1 for ev in bundle.evidence if ev.reviewer),
        "evidence_rows": len(bundle.evidence),
        "evidence_citing_an_unverified_source": sum(1 for ev in bundle.evidence if sources.get(ev.source_id) is not None and not sources[ev.source_id].verified),
        "evidence_citing_a_missing_source": sum(1 for ev in bundle.evidence if ev.source_id not in sources),
    }

    # confidence
    tiers = Counter(c.tier.value for c in claims if c.tier is not None)
    by_type_tier: dict[str, Counter] = defaultdict(Counter)
    for c in claims:
        if c.tier is not None:
            by_type_tier[c.type.value][c.tier.value] += 1
    conflicts = []
    for c in claims:
        if c.conflict:
            conflicts.append((entities[c.subject_id].name if c.subject_id in entities else c.subject_id, entities[c.object_id].name if c.object_id in entities else c.object_id,
                              c.qualifiers.get("reaction"), c.qualifiers.get("season") or c.qualifiers.get("location") or ""))
    report["confidence"] = {"tiers": dict(sorted(tiers.items())), "tiers_by_claim_type": {k: dict(sorted(v.items())) for k, v in sorted(by_type_tier.items())},
                            "conflicts": len(conflicts), "conflict_examples": sorted(conflicts)[:15]}

    # staleness: evidence on race-structured diseases older than the cut-off (the x0.8 factor applies to it)
    stale = 0
    race = 0
    for c in claims:
        if scoring._pathotype_dependent(c):
            for ev in by_claim[c.id]:
                race += 1
                src = sources.get(ev.source_id)
                if src is not None and src.year and scoring.date.today().year - src.year > scoring.STALE_PATHOTYPE_YEARS:
                    stale += 1
    report["staleness"] = {"evidence_rows_on_race_structured_claims": race, "of_which_older_than_10_years": stale}

    # coverage per crop
    cov: dict = {}
    varieties = [e for e in bundle.entities if e.type.value == "Variety"]
    for crop in ("wheat", "soybean", "chickpea"):
        vs = {e.id for e in varieties if e.crop and e.crop.value == crop}
        has = lambda ctype: {c.subject_id for c in claims if c.type.value == ctype and c.subject_id in vs}  # noqa: E731
        reactions, genes, zones = has("VARIETY_REACTION"), has("VARIETY_CARRIES_GENE"), has("VARIETY_RECOMMENDED_FOR_ZONE")
        cov[crop] = {"varieties": len(vs), "with_a_reaction": len(reactions), "with_a_gene": len(genes), "with_a_zone": len(zones),
                     "with_reaction_and_gene": len(reactions & genes), "with_none_of_these": len(vs - reactions - genes - zones),
                     "reaction_claims": sum(1 for c in claims if c.type.value == "VARIETY_REACTION" and c.subject_id in vs)}
    report["variety_coverage"] = cov

    diseases = [e for e in bundle.entities if e.type.value == "Disease"]
    rows = []
    for d in sorted(diseases, key=lambda e: (e.crop.value if e.crop else "", e.name)):
        def count(ctype, role="object_id", dist=False, d=d):
            items = [(getattr(c, role)) for c in claims if c.type.value == ctype and c.object_id == d.id]
            return len(set(items)) if dist else len(items)
        rows.append({"crop": d.crop.value if d.crop else "", "disease": d.name,
                     "varieties_with_reaction": len({c.subject_id for c in claims if c.type.value == "VARIETY_REACTION" and c.object_id == d.id}),
                     "genes": len({c.subject_id for c in claims if c.type.value == "GENE_CONFERS_RESISTANCE" and c.object_id == d.id}),
                     "qtl_loci": count("QTL_ASSOCIATION"), "triggers": len([c for c in claims if c.type.value == "DISEASE_ENV_TRIGGER" and c.subject_id == d.id]),
                     "advisories": len([c for c in claims if c.type.value == "DISEASE_MANAGED_BY" and c.subject_id == d.id]),
                     "pathogens": len([c for c in claims if c.type.value == "DISEASE_CAUSED_BY" and c.subject_id == d.id])})
    report["disease_coverage"] = rows
    report["disease_gaps"] = [f"{r['crop']} {r['disease']}: no " + ", ".join(k.replace("_", " ") for k in ("varieties_with_reaction", "genes", "qtl_loci", "triggers", "advisories") if not r[k])
                              for r in rows if any(not r[k] for k in ("varieties_with_reaction", "genes", "qtl_loci", "triggers", "advisories"))]

    # structural checks
    referenced = {c.subject_id for c in claims} | {c.object_id for c in claims}
    orphans = Counter(e.type.value for e in bundle.entities if e.id not in referenced)
    keyed: dict[tuple, list] = defaultdict(list)
    for e in bundle.entities:
        for n in [e.name, *e.synonyms]:
            keyed[(e.type.value, e.crop.value if e.crop else None, lookup_key(n))].append(e.id)
    collisions = sorted({tuple(sorted(set(ids))) for ids in keyed.values() if len(set(ids)) > 1})
    report["structure"] = {"orphan_entities_by_type": dict(orphans), "name_collisions": [list(c) for c in collisions[:20]], "name_collision_count": len(collisions)}

    # targets
    tg = {"varieties": {c: (cov[c]["varieties"], TARGETS["varieties"][c]) for c in cov},
          "reaction_claims": (sum(v["reaction_claims"] for v in cov.values()), TARGETS["reaction_claims"]),
          "wheat_genes": (report["entities"].get("Gene", 0) and len([e for e in bundle.entities if e.type.value == "Gene" and e.crop and e.crop.value == "wheat"]), TARGETS["wheat_genes"]),
          "soybean_loci": (len([e for e in bundle.entities if e.type.value in ("Gene", "QTL") and e.crop and e.crop.value == "soybean"]), TARGETS["soybean_loci"]),
          "chickpea_qtls": (len([e for e in bundle.entities if e.type.value == "QTL" and e.crop and e.crop.value == "chickpea"]), TARGETS["chickpea_qtls"]),
          "human_reviewed_share": (round(report["provenance"]["human_reviewed_evidence"] / max(1, len(bundle.evidence)), 3), 0.8)}
    report["targets"] = tg
    return report


# ───────────────────────────── sensitivity ─────────────────────────────
@dataclass(frozen=True)
class Scenario:
    name: str
    llm_factor: float = scoring.LLM_UNREVIEWED_FACTOR
    stale_factor: float = scoring.STALE_PATHOTYPE_FACTOR
    weight_scale: float = 1.0
    threshold_shift: float = 0.0


SCENARIOS = [
    Scenario("model-evidence discount 0.4 (harsher)", llm_factor=0.4),
    Scenario("model-evidence discount 0.8 (milder)", llm_factor=0.8),
    Scenario("no model-evidence discount (1.0)", llm_factor=1.0),
    Scenario("staleness factor 0.6 (harsher)", stale_factor=0.6),
    Scenario("no staleness discount (1.0)", stale_factor=1.0),
    Scenario("all evidence weights -20 %", weight_scale=0.8),
    Scenario("all evidence weights +20 % (capped at 1)", weight_scale=1.2),
    Scenario("tier cut-offs +0.05", threshold_shift=0.05),
    Scenario("tier cut-offs -0.05", threshold_shift=-0.05),
]


@contextmanager
def _patched(s: Scenario):
    saved = (scoring.LLM_UNREVIEWED_FACTOR, scoring.STALE_PATHOTYPE_FACTOR, scoring.TIER_THRESHOLDS, dict(EVIDENCE_WEIGHT))
    try:
        scoring.LLM_UNREVIEWED_FACTOR, scoring.STALE_PATHOTYPE_FACTOR = s.llm_factor, s.stale_factor
        scoring.TIER_THRESHOLDS = tuple((t, floor + s.threshold_shift) for t, floor in saved[2])
        for k, v in saved[3].items():
            EVIDENCE_WEIGHT[k] = min(1.0, v * s.weight_scale)
        yield
    finally:
        scoring.LLM_UNREVIEWED_FACTOR, scoring.STALE_PATHOTYPE_FACTOR, scoring.TIER_THRESHOLDS = saved[0], saved[1], saved[2]
        EVIDENCE_WEIGHT.update(saved[3])


def sensitivity(bundle: KGBundle, *, as_of_year: int | None = None) -> dict:
    base = scoring.score_bundle(bundle, as_of_year=as_of_year)
    base_tier = {c.id: c.tier for c in base.claims if c.tier is not None}
    order = {Tier.A: 0, Tier.B: 1, Tier.C: 2, Tier.D: 3}
    out = {"baseline": dict(sorted(Counter(t.value for t in base_tier.values()).items())), "scenarios": []}
    for s in SCENARIOS:
        with _patched(s):
            scored = scoring.score_bundle(bundle, as_of_year=as_of_year)
        tiers = {c.id: c.tier for c in scored.claims if c.tier is not None}
        changed = [cid for cid, t in tiers.items() if t != base_tier.get(cid)]
        up = sum(1 for cid in changed if order[tiers[cid]] < order[base_tier[cid]])
        out["scenarios"].append({"scenario": s.name, "tiers": dict(sorted(Counter(t.value for t in tiers.values()).items())), "claims_changing_tier": len(changed),
                                 "share_changing": round(len(changed) / max(1, len(tiers)), 4), "moving_up": up, "moving_down": len(changed) - up})
    return out


# ───────────────────────────── Markdown ─────────────────────────────
def to_markdown(report: dict, sens: dict, *, release: str = "") -> str:
    L: list[str] = []
    w = L.append
    w(f"# Knowledge graph QC report{f' ({release})' if release else ''}\n")
    w("Generated by `agrihub kg qc` (curator/graph/qc.py). Nothing here is hand-written.\n")
    w("## Scale\n")
    w("| | |\n|---|---|")
    w(f"| Entities | {sum(report['entities'].values())} ({', '.join(f'{k} {v}' for k, v in report['entities'].items())}) |")
    w(f"| Claims | {report['provenance']['claims']} |")
    w(f"| Evidence rows | {report['provenance']['evidence_rows']} |")
    w(f"| Sources | {sum(report['sources_by_type'].values())} ({', '.join(f'{k} {v}' for k, v in report['sources_by_type'].items())}) |\n")
    w("## Provenance\n")
    p = report["provenance"]
    w("| Check | Count |\n|---|---|")
    w(f"| Claims without evidence | {p['without_evidence']} |")
    w(f"| Evidence citing an unverified source | {p['evidence_citing_an_unverified_source']} |")
    w(f"| Evidence citing a missing source | {p['evidence_citing_a_missing_source']} |")
    w(f"| Claims resting only on model-found (`llm:`) evidence | {p['with_only_model_found_evidence']} ({p['with_only_model_found_evidence'] * 100 // max(1, p['claims'])} %) |")
    w(f"| Claims with one source / two or more | {p['with_one_source']} / {p['with_two_or_more_sources']} |")
    w(f"| Human-reviewed evidence rows | {p['human_reviewed_evidence']} |\n")
    w("Evidence by method: " + ", ".join(f"{k} {v}" for k, v in report["evidence_by_method"].items()) + "\n")
    w("Evidence by extractor family: " + ", ".join(f"{k} {v}" for k, v in report["evidence_by_extractor"].items()) + "\n")
    c = report["confidence"]
    w("## Confidence\n")
    w("Tiers: " + ", ".join(f"{k} {v}" for k, v in c["tiers"].items()) + f"; {c['conflicts']} claims are flagged as conflicting (capped at tier C).\n")
    w("| Claim type | A | B | C | D |\n|---|---|---|---|---|")
    for k, v in c["tiers_by_claim_type"].items():
        w(f"| {k} | {v.get('A', 0)} | {v.get('B', 0)} | {v.get('C', 0)} | {v.get('D', 0)} |")
    w("\nExamples of conflicting readings: " + "; ".join(f"{a} / {b} {r or ''} {s}".strip() for a, b, r, s in c["conflict_examples"][:8]) + "\n")
    st = report["staleness"]
    w(f"Staleness: {st['of_which_older_than_10_years']} of {st['evidence_rows_on_race_structured_claims']} evidence rows on race-structured claims are more than 10 years old (they carry the x0.8 factor).\n")
    w("## Coverage\n")
    w("| Crop | Varieties | With a reaction | With a gene | With a zone | With none of these | Reaction claims |\n|---|---|---|---|---|---|---|")
    for crop, v in report["variety_coverage"].items():
        w(f"| {crop} | {v['varieties']} | {v['with_a_reaction']} | {v['with_a_gene']} | {v['with_a_zone']} | {v['with_none_of_these']} | {v['reaction_claims']} |")
    w("\n| Crop | Disease | Varieties with a reaction | Genes | QTL loci | Triggers | Advisories | Pathogens |\n|---|---|---|---|---|---|---|---|")
    for r in report["disease_coverage"]:
        w(f"| {r['crop']} | {r['disease']} | {r['varieties_with_reaction']} | {r['genes']} | {r['qtl_loci']} | {r['triggers']} | {r['advisories']} | {r['pathogens']} |")
    w("\nGaps: " + ("; ".join(report["disease_gaps"]) if report["disease_gaps"] else "none") + "\n")
    s = report["structure"]
    w("## Structure\n")
    w(f"Orphan entities (referenced by no claim): {s['orphan_entities_by_type'] or 'none'}. Name collisions (two entities of one type and crop sharing a lookup key): {s['name_collision_count']}"
      + (f" ({'; '.join(' / '.join(x) for x in s['name_collisions'][:6])})" if s['name_collisions'] else "") + ".\n")
    w("## Against the roadmap targets\n")
    w("| Target | Now | Goal |\n|---|---|---|")
    for crop, (now, goal) in report["targets"]["varieties"].items():
        w(f"| Varieties, {crop} | {now} | {goal} |")
    for key in ("reaction_claims", "wheat_genes", "soybean_loci", "chickpea_qtls", "human_reviewed_share"):
        now, goal = report["targets"][key]
        w(f"| {key.replace('_', ' ')} | {now} | {goal} |")
    w("\n## Sensitivity of the tiers to the scoring constants\n")
    w("The graph is re-scored under alternative parameters; a robust tier assignment moves few claims.\n")
    w("Baseline tiers: " + ", ".join(f"{k} {v}" for k, v in sens["baseline"].items()) + "\n")
    w("| Scenario | A | B | C | D | Claims changing tier | Share | Up | Down |\n|---|---|---|---|---|---|---|---|---|")
    for s_ in sens["scenarios"]:
        t = s_["tiers"]
        w(f"| {s_['scenario']} | {t.get('A', 0)} | {t.get('B', 0)} | {t.get('C', 0)} | {t.get('D', 0)} | {s_['claims_changing_tier']} | {s_['share_changing'] * 100:.1f} % | {s_['moving_up']} | {s_['moving_down']} |")
    return "\n".join(L) + "\n"
