"""Research outputs computed from the curated graph (RESEARCH_ROADMAP.md phase 12), as descriptive tables, never as new facts in the graph:

- multi-disease donors: varieties with a resistant (R/MR) reading to every wheat rust, with the tier of each reading and whether any reading conflicts;
- gene deployment: how concentrated the rust-resistance genes are among the varieties recommended for each zone (the "Lr26/Sr31/Yr9 legacy" question);
- pathotype dynamics: the dominant stripe-rust and stem-rust pathotypes by state and season from the surveillance tables, and the national trend of each;
- knowledge gaps: widely recommended varieties with no recorded reaction to a disease, and diseases with the thinnest evidence;
- an observed susceptibility index per wheat variety: the share of its rust readings that are susceptible. It is NOT the roadmap's Variety Vulnerability Index (that also needs
  weather-window frequency and pathotype-virulence data, which the graph does not hold).
`agrihub kg analytics` renders them to Markdown.
"""

from __future__ import annotations

from collections import Counter, defaultdict

import curator.model  # noqa: F401
from curator.graph.bundle import KGBundle

RUSTS = {"dis:wheat:stem_rust": "stem rust", "dis:wheat:leaf_rust": "leaf rust", "dis:wheat:stripe_rust": "stripe rust"}
RESISTANT, SUSCEPTIBLE = {"R", "MR"}, {"MS", "S", "HS"}
TIER_RANK = {"A": 0, "B": 1, "C": 2, "D": 3}


def _name(entities, entity_id):
    e = entities.get(entity_id)
    return e.name if e else entity_id


def analytics(bundle: KGBundle) -> dict:
    ent = {e.id: e for e in bundle.entities}
    claims = bundle.claims
    out: dict = {}

    # readings per (variety, rust)
    readings: dict[tuple[str, str], list] = defaultdict(list)
    for c in claims:
        if c.type.value == "VARIETY_REACTION" and c.object_id in RUSTS:
            readings[(c.subject_id, c.object_id)].append(c)

    donors = []
    for v in {k[0] for k in readings}:
        per = {}
        for d in RUSTS:
            rs = readings.get((v, d), [])
            if not rs:
                break
            res = [r for r in rs if r.qualifiers.get("reaction") in RESISTANT]
            if not res:
                break
            best = min(res, key=lambda r: TIER_RANK[r.tier.value] if r.tier else 9)
            per[d] = (best.tier.value if best.tier else "?", any(r.conflict for r in rs), len(rs), sum(1 for r in rs if r.qualifiers.get("reaction") in SUSCEPTIBLE))
        else:
            donors.append({"variety": _name(ent, v), "tiers": {RUSTS[d]: per[d][0] for d in per}, "conflict": any(per[d][1] for d in per),
                           "readings": sum(per[d][2] for d in per), "susceptible_readings": sum(per[d][3] for d in per)})
    donors.sort(key=lambda r: (r["conflict"], r["susceptible_readings"], -r["readings"], r["variety"]))
    out["multi_rust_donors"] = donors

    # observed susceptibility index
    idx = []
    for v in {k[0] for k in readings}:
        rs = [r for d in RUSTS for r in readings.get((v, d), []) if r.qualifiers.get("reaction")]
        if len(rs) >= 3:
            s = sum(1 for r in rs if r.qualifiers["reaction"] in SUSCEPTIBLE)
            idx.append({"variety": _name(ent, v), "readings": len(rs), "susceptible_share": round(s / len(rs), 2)})
    idx.sort(key=lambda r: (-r["susceptible_share"], -r["readings"]))
    out["susceptibility_index"] = {"most_susceptible": idx[:15], "least_susceptible": sorted(idx, key=lambda r: (r["susceptible_share"], -r["readings"]))[:15], "n_varieties": len(idx)}

    # gene deployment per zone
    zones_of: dict[str, set] = defaultdict(set)
    for c in claims:
        if c.type.value == "VARIETY_RECOMMENDED_FOR_ZONE":
            zones_of[c.subject_id].add(c.object_id)
    genes_of: dict[str, set] = defaultdict(set)
    for c in claims:
        if c.type.value == "VARIETY_CARRIES_GENE":
            genes_of[c.subject_id].add(c.object_id)
    deploy = []
    for z in sorted({z for zs in zones_of.values() for z in zs}):
        vs = [v for v, zs in zones_of.items() if z in zs and genes_of.get(v)]
        if len(vs) < 3:
            continue
        counts = Counter(g for v in vs for g in genes_of[v])
        top = counts.most_common(4)
        shares = [n / len(vs) for n in counts.values()]
        deploy.append({"zone": _name(ent, z), "varieties_with_genes": len(vs), "top_genes": [(_name(ent, g), n, round(n / len(vs), 2)) for g, n in top],
                       "legacy_translocation_share": round(sum(1 for v in vs if any(_name(ent, g) in ("Sr31", "Lr26", "Yr9") for g in genes_of[v])) / len(vs), 2),
                       "concentration_hhi": round(sum(s * s for s in shares) / max(1, len(shares)), 3)})
    out["gene_deployment"] = deploy

    # pathotype dynamics
    prev = defaultdict(list)
    for c in claims:
        if c.type.value == "PATHOTYPE_PREVALENCE":
            prev[(c.subject_id, c.object_id)].append((c.qualifiers["years"][0], c.qualifiers.get("frequency_pct")))
    by_state_year: dict[tuple, list] = defaultdict(list)
    for (pt, z), items in prev.items():
        for year, pct in items:
            by_state_year[(z, year, pt.split(":")[1])].append((pct, pt))
    dominant = []
    for (z, year, pathogen), items in sorted(by_state_year.items(), key=lambda kv: (kv[0][2], kv[0][0], kv[0][1])):
        pct, pt = max(items)
        dominant.append({"pathogen": pathogen.replace("puccinia_", "P. ").replace("_f_sp_tritici", " f. sp. tritici"), "state": _name(ent, z).replace(" (wheat)", ""), "season_end": year,
                         "dominant_pathotype": _name(ent, pt), "share_pct": pct})
    out["dominant_pathotypes"] = dominant
    nat = defaultdict(lambda: defaultdict(list))
    for (pt, z), items in prev.items():
        for year, pct in items:
            nat[pt][year].append(pct)
    out["pathotype_trend"] = sorted(({"pathotype": _name(ent, pt), "by_season_end": {y: round(sum(v) / len(v), 1) for y, v in sorted(ys.items())}} for pt, ys in nat.items() if len(ys) >= 2),
                                    key=lambda r: r["pathotype"])

    # knowledge gaps: recommended varieties without a reaction to a disease of their crop
    diseases_by_crop = defaultdict(list)
    for e in bundle.entities:
        if e.type.value == "Disease" and e.crop:
            diseases_by_crop[e.crop.value].append(e.id)
    reacted = defaultdict(set)
    for c in claims:
        if c.type.value == "VARIETY_REACTION":
            reacted[c.subject_id].add(c.object_id)
    gaps = []
    for v, zs in zones_of.items():
        e = ent.get(v)
        if e is None or not e.crop:
            continue
        missing = [d for d in diseases_by_crop[e.crop.value] if d not in reacted[v]]
        if missing and len(zs) >= 2:
            gaps.append({"variety": e.name, "crop": e.crop.value, "zones": len(zs), "diseases_without_reading": len(missing), "of": len(diseases_by_crop[e.crop.value])})
    gaps.sort(key=lambda r: (-r["zones"], -r["diseases_without_reading"], r["variety"]))
    out["recommended_but_untested"] = gaps[:20]
    return out


def to_markdown(a: dict, *, release: str = "") -> str:
    L: list[str] = []
    w = L.append
    w(f"# Analytics from the knowledge graph{f' ({release})' if release else ''}\n")
    w("Generated by `agrihub kg analytics` (curator/graph/analytics.py). These are descriptive tables over the curated claims, not new facts: every row can be traced to claims with evidence. "
      "Tiers are the claims' own (A strongest, D weakest).\n")
    w("## Wheat varieties resistant (R or MR) to all three rusts\n")
    w("Varieties with at least one resistant reading for stem, leaf and stripe rust. Sorted by fewest conflicting / susceptible readings first. A \"conflict\" means other readings disagree.\n")
    w("| Variety | Stem rust tier | Leaf rust tier | Stripe rust tier | Readings | Susceptible readings | Conflict |\n|---|---|---|---|---|---|---|")
    for r in a["multi_rust_donors"][:40]:
        t = r["tiers"]
        w(f"| {r['variety']} | {t.get('stem rust')} | {t.get('leaf rust')} | {t.get('stripe rust')} | {r['readings']} | {r['susceptible_readings']} | {'yes' if r['conflict'] else ''} |")
    w(f"\n{len(a['multi_rust_donors'])} varieties in all.\n")
    s = a["susceptibility_index"]
    w("## Observed rust susceptibility (not the full Variety Vulnerability Index)\n")
    w(f"Share of a variety's rust readings (at least three) that are susceptible; {s['n_varieties']} varieties qualify. The roadmap's VVI also needs weather-window frequency and pathotype virulence, which the graph does not hold.\n")
    w("Most often susceptible: " + "; ".join(f"{r['variety']} {int(r['susceptible_share'] * 100)} % of {r['readings']}" for r in s["most_susceptible"][:12]) + "\n")
    w("Least often susceptible: " + "; ".join(f"{r['variety']} {int(r['susceptible_share'] * 100)} % of {r['readings']}" for r in s["least_susceptible"][:12]) + "\n")
    w("## Rust-gene deployment by zone\n")
    w("Among varieties recommended for a zone that carry at least one recorded gene: the most common genes, the share carrying the Sr31 / Lr26 / Yr9 rye translocation (the legacy resistance Ug99 threatened), and the Herfindahl concentration of gene use (1 = all varieties share one gene). Only varieties with gene records are counted, so read these as the genes we know about.\n")
    w("| Zone | Varieties with genes | Most common genes (count, share) | Sr31/Lr26/Yr9 share | Concentration |\n|---|---|---|---|---|")
    for r in a["gene_deployment"]:
        w(f"| {r['zone']} | {r['varieties_with_genes']} | {', '.join(f'{g} ({n}, {int(sh * 100)} %)' for g, n, sh in r['top_genes'])} | {int(r['legacy_translocation_share'] * 100)} % | {r['concentration_hhi']} |")
    w("\n## Dominant rust pathotypes by state and season\n")
    w("| Pathogen | State | Season (end year) | Dominant pathotype | Share of isolates |\n|---|---|---|---|---|")
    for r in a["dominant_pathotypes"]:
        w(f"| {r['pathogen']} | {r['state']} | {r['season_end']} | {r['dominant_pathotype']} | {r['share_pct']} % |")
    w("\nPathotypes seen in more than one season (mean share of isolates across states, by season end year): " + "; ".join(
        f"{r['pathotype']} " + ", ".join(f"{y}: {v} %" for y, v in r["by_season_end"].items()) for r in a["pathotype_trend"]) + "\n")
    w("## Recommended varieties with the most unrecorded disease readings\n")
    w("Varieties recommended for two or more zones but with no recorded reaction to some in-scope disease of their crop: where screening data would help most.\n")
    w("| Variety | Crop | Zones | Diseases without a reading |\n|---|---|---|---|")
    for r in a["recommended_but_untested"]:
        w(f"| {r['variety']} | {r['crop']} | {r['zones']} | {r['diseases_without_reading']} of {r['of']} |")
    return "\n".join(L) + "\n"
