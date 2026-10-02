"""Assemble ready-to-paste research prompts: tool preamble + shared spec (filled from the LIVE KB) + one work order.

    python tools/build_research_prompts.py            # writes docs/research_prompts/ready/<WO>_<tool>.md

The vocabulary, known varieties and the "where the KB is thin" table are regenerated from the current bundle each time, so
re-run this before every research session; the prompt then never asks for what the KB already has plenty of.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from curator.cli import _build_bundle  # noqa: E402

DIR = REPO / "docs" / "research_prompts"
OUT = DIR / "ready"


def _vocab_tables(bundle) -> dict[str, str]:
    vocab = yaml.safe_load((REPO / "config" / "vocab" / "diseases.yaml").read_text(encoding="utf-8"))["diseases"]
    rows = ["| id | name | also accepted |", "|---|---|---|"]
    for d in vocab:
        if d["id"].endswith(":rusts"):
            continue
        syn = ", ".join(d.get("synonyms", [])) or "-"
        rows.append(f"| `{d['id']}` | {d['name']} | {syn} |")
    rows.append("")
    rows.append("Wheat synonyms the pipeline also understands: brown rust = leaf rust, black rust = stem rust, yellow rust = stripe rust.")
    pathogens = [f"- `{e.id}` ({e.name})" for e in bundle.entities if e.type.value == "Pathogen"]
    by_crop: dict[str, list[str]] = {}
    for e in bundle.entities:
        if e.type.value == "Variety":
            by_crop.setdefault(e.crop.value, []).append(e.name)
    varieties = "\n".join(f"- **{crop}** ({len(names)}): " + "; ".join(sorted(names)) for crop, names in sorted(by_crop.items()))
    genes = ", ".join(sorted(f"{e.name} ({e.crop.value})" for e in bundle.entities if e.type.value == "Gene"))
    zone_rows = ["| zone id | name | also accepted | definition (from the KG's source) |", "|---|---|---|---|"]
    for e in sorted((e for e in bundle.entities if e.type.value == "AgroZone"), key=lambda e: e.id):
        definition = (e.props.get("definition") or "state-level zone").replace("|", "/")
        zone_rows.append(f"| `{e.id}` | {e.name} | {', '.join(e.synonyms) or '-'} | {definition} |")
    return {"DISEASES": "\n".join(rows), "PATHOGENS": "\n".join(pathogens), "KNOWN_VARIETIES": varieties,
            "KNOWN_GENES": genes, "ZONES": "\n".join(zone_rows)}


def _coverage(bundle) -> str:
    names = {e.id: e.name for e in bundle.entities}
    react, genes, advisories = Counter(), Counter(), Counter()
    for c in bundle.claims:
        if c.type.value == "VARIETY_REACTION":
            react[c.object_id] += 1
        elif c.type.value == "GENE_CONFERS_RESISTANCE":
            genes[c.object_id] += 1
        elif c.type.value == "DISEASE_MANAGED_BY":
            advisories[c.subject_id] += 1
    disease_ids = sorted(e.id for e in bundle.entities if e.type.value == "Disease" and not e.id.endswith(":rusts"))
    rows = ["| disease | variety reactions | resistance genes | advisories |", "|---|---|---|---|"]
    for d in sorted(disease_ids, key=lambda i: react[i] + genes[i] + advisories[i]):
        rows.append(f"| {names[d]} (`{d}`) | {react[d]} | {genes[d]} | {advisories[d]} |")
    total = Counter(c.type.value for c in bundle.claims)
    rows.append("")
    rows.append(f"Total claims now: {len(bundle.claims)} (" + ", ".join(f"{k} {v}" for k, v in total.most_common()) + ").")
    return "\n".join(rows)


def _work_orders() -> list[tuple[str, str, str, str]]:
    text = (DIR / "work_orders.md").read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r"^## (WO\d+) \| (chatgpt|grok|both) \| (.+?)\n(.*?)(?=^## WO|\Z)", text, flags=re.S | re.M):
        lines = [line for line in m.group(4).splitlines() if not line.startswith(">")]  # ">" lines are notes for people
        body = chr(10).join(lines).strip()
        out.append((m.group(1), m.group(2), m.group(3).strip(), body))
    return out


def main() -> None:
    bundle = _build_bundle()
    spec = (DIR / "_shared_spec.md").read_text(encoding="utf-8")
    fill = {**_vocab_tables(bundle), "COVERAGE": _coverage(bundle), "TODAY": date.today().isoformat()}
    for key, value in fill.items():
        spec = spec.replace("{{" + key + "}}", value)
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.md"):
        old.unlink()
    written = []
    for wo, tool, title, body in _work_orders():
        for t in (("chatgpt", "grok") if tool == "both" else (tool,)):
            preamble = (DIR / f"_preamble_{t}.md").read_text(encoding="utf-8")
            work = f"### {wo} - {title}\n\nUse `{wo}` as the work order id in every candidate_id and in batch_id.\n\n{body}"
            prompt = preamble.rstrip() + "\n\n---\n\n" + spec.replace("{{WORK_ORDER}}", work)
            path = OUT / f"{wo}_{t}.md"
            path.write_text(prompt, encoding="utf-8", newline="\n")
            written.append((path.name, len(prompt)))
    for name, size in written:
        print(f"{name:28s} {size:>7,d} chars (~{size // 4:,d} tokens)")


if __name__ == "__main__":
    main()
