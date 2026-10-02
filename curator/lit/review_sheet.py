"""Human review of an ingested batch, by spreadsheet.

The bottleneck of scaling the KB is not finding claims, it is somebody who knows the crop reading them. So the review
asks the least possible of that person: open a CSV in Excel or Google Sheets, read a plain sentence, a verbatim quote and
a clickable source link, type OK / WRONG / UNSURE (and, for advisories, whether the dose and timing fit Malwa).

    agrihub kg review-sheet kg/incoming/WO03.yaml      -> kg/incoming/WO03.review.csv   (send this to the reviewer)
    agrihub kg apply-review kg/incoming/WO03.yaml kg/incoming/WO03.review.csv --reviewer "Name"

The sheet marks a random SAMPLE (max(10, 10 % of the batch), advisories over-represented because a wrong dose does the
most harm). apply-review refuses the batch unless every sample row has a verdict and at most 5 % of the sample is not
confirmed (UNSURE counts against the batch: a claim the reviewer could not confirm is not confirmed). When the batch passes:
rows marked WRONG/UNSURE, and advisories marked local_fit NO, are held back; rows marked OK get the reviewer's name and
date (so the scoring layer drops its model-evidence discount) and status `reviewed`; the rest enter unreviewed.
"""

from __future__ import annotations

import csv
import hashlib
import math
import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from curator.graph.bundle import KGBundle
from curator.model import Claim

SAMPLE_MIN = 10
SAMPLE_RATE = 0.10
MAX_WRONG_SHARE = 0.05
VERDICTS = {"OK", "WRONG", "UNSURE"}
LOCAL_FIT = {"YES", "NO", "UNSURE"}
PRIORITY = {"DISEASE_MANAGED_BY": 0, "DISEASE_ENV_TRIGGER": 0}  # advisories first: a wrong dose does the most harm

COLUMNS = [
    "row_id", "in_sample", "crop", "claim_type", "the_claim_in_words", "advisory_product_dose_timing", "qualifiers",
    "quote", "source_title", "source_link", "locator", "evidence_method",
    "verdict", "local_fit", "comment", "reviewer_name",
    "claim_id", "source_id", "quote_key",
]

PHRASES = {
    "VARIETY_REACTION": "{s} is {reaction} to {o}",
    "VARIETY_CARRIES_GENE": "{s} carries the gene {o}",
    "VARIETY_RECOMMENDED_FOR_ZONE": "{s} is recommended for {o}",
    "VARIETY_DERIVED_FROM": "{s} was derived from {o} ({role})",
    "GENE_CONFERS_RESISTANCE": "{s} confers resistance to {o}",
    "GENE_PATHOTYPE_INTERACTION": "{s} is {outcome} against {o}",
    "QTL_ASSOCIATION": "{s} is associated with resistance to {o}",
    "MARKER_LINKAGE": "marker {s} is linked to {o}",
    "PATHOTYPE_VARIANT_OF": "{s} is a pathotype of {o}",
    "PATHOTYPE_PREVALENCE": "{s} occurs in {o}",
    "DISEASE_CAUSED_BY": "{s} is caused by {o}",
    "DISEASE_MANAGED_BY": "For {s}: {o}",
    "DISEASE_ENV_TRIGGER": "{s} is triggered by {o}",
}


class ReviewError(ValueError):
    """The review cannot be applied as it stands (message says why)."""


def quote_key(quote: str | None) -> str:
    return hashlib.sha1((quote or "").encode("utf-8")).hexdigest()[:10]


def _context(q: dict[str, Any]) -> str:
    parts = [f"{k}: {v}" for k, v in q.items() if k not in ("reaction",) and v not in (None, "", "unspecified")]
    return "; ".join(parts)


def _sentence(claim_type: str, subject: str, obj: str, q: dict[str, Any]) -> str:
    base = PHRASES.get(claim_type, "{s} -[" + claim_type + "]-> {o}").format(
        s=subject, o=obj, reaction=q.get("reaction", "?"), role=q.get("role", ""), outcome=q.get("outcome", ""))
    ctx = _context(q)
    return f"{base}  ({ctx})" if ctx else base


def _source_link(source: dict[str, Any] | None, source_id: str) -> str:
    if source and source.get("url"):
        return source["url"]
    if source_id.startswith("pmid:"):
        return f"https://pubmed.ncbi.nlm.nih.gov/{source_id[5:]}/"
    return ""


def read_batch(path: Path) -> dict[str, Any]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {"sources": doc.get("sources") or [], "entities": doc.get("entities") or [], "claims": doc.get("claims") or []}


def _rows(batch: dict[str, Any], bundle: KGBundle) -> list[dict[str, Any]]:
    names = {e.id: e for e in bundle.entities} | {e["id"]: type("E", (), {"name": e["name"], "props": e.get("props", {})}) for e in batch["entities"]}
    sources = {s.id: s.model_dump() for s in bundle.sources} | {s["id"]: s for s in batch["sources"]}
    rows = []
    for spec in batch["claims"]:
        claim = Claim(type=spec["type"], subject_id=spec["subject"], object_id=spec["object"], qualifiers=spec.get("qualifiers") or {})
        subject, obj = names[spec["subject"]], names[spec["object"]]
        props = getattr(obj, "props", {}) or {}
        advisory = ""
        if spec["type"] == "DISEASE_MANAGED_BY":
            advisory = " | ".join(f"{k}: {props[k]}" for k in ("action_type", "active_ingredient", "dose", "timing", "region") if props.get(k))
        for ev in spec["evidence"]:
            src = sources.get(ev["source"])
            rows.append({
                "row_id": ev.get("candidate_id") or f"{claim.id}:{ev['source']}",
                "in_sample": "", "crop": (subject.crop.value if getattr(subject, "crop", None) else ""),
                "claim_type": spec["type"], "the_claim_in_words": _sentence(spec["type"], subject.name, obj.name, claim.qualifiers),
                "advisory_product_dose_timing": advisory, "qualifiers": _context(claim.qualifiers),
                "quote": ev.get("quote") or "", "source_title": (src or {}).get("title", ev["source"]),
                "source_link": _source_link(src, ev["source"]), "locator": ev.get("locator") or "", "evidence_method": ev["method"],
                "verdict": "", "local_fit": "", "comment": "", "reviewer_name": "",
                "claim_id": claim.id, "source_id": ev["source"], "quote_key": quote_key(ev.get("quote")),
            })
    return rows


def sample_size(n: int, rate: float = SAMPLE_RATE) -> int:
    return min(n, max(SAMPLE_MIN, math.ceil(n * rate)))


def make_sheet(batch_path: Path, bundle: KGBundle, out: Path, *, rate: float = SAMPLE_RATE, seed: int = 7, everything: bool = False) -> dict[str, int]:
    rows = _rows(read_batch(batch_path), bundle)
    rng = random.Random(seed)
    k = len(rows) if everything else sample_size(len(rows), rate)
    # advisories are twice as likely to be drawn: shuffle with a head start
    ordered = sorted(rows, key=lambda r: rng.random() - (0.5 if r["claim_type"] in PRIORITY else 0.0))
    chosen = {r["row_id"] for r in ordered[:k]}
    for r in rows:
        r["in_sample"] = "YES" if r["row_id"] in chosen else ""
    rows.sort(key=lambda r: (r["in_sample"] != "YES", PRIORITY.get(r["claim_type"], 1), r["crop"], r["the_claim_in_words"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as fh:  # BOM so Excel reads UTF-8
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return {"rows": len(rows), "sample": len(chosen)}


@dataclass
class AppliedReview:
    accepted_claims: int
    reviewed_claims: int
    held: list[dict[str, str]]
    sample_n: int
    sample_not_ok: int


def apply_review(batch_path: Path, sheet_path: Path, out: Path, *, reviewer: str | None = None, today: date | None = None) -> AppliedReview:
    batch = read_batch(batch_path)
    with sheet_path.open(encoding="utf-8-sig", newline="") as fh:
        sheet = list(csv.DictReader(fh))
    by_key = {(r["claim_id"], r["source_id"], r["quote_key"]): r for r in sheet}

    sample = [r for r in sheet if r["in_sample"].strip().upper() == "YES"]
    if not sample:
        raise ReviewError("the sheet has no rows marked in_sample=YES; regenerate it with `agrihub kg review-sheet`")
    for r in sheet:
        v = r["verdict"].strip().upper()
        if v and v not in VERDICTS:
            raise ReviewError(f"row {r['row_id']}: verdict {r['verdict']!r} is not one of OK / WRONG / UNSURE")
        lf = r["local_fit"].strip().upper()
        if lf and lf not in LOCAL_FIT:
            raise ReviewError(f"row {r['row_id']}: local_fit {r['local_fit']!r} is not one of YES / NO / UNSURE")
    missing = [r["row_id"] for r in sample if not r["verdict"].strip()]
    if missing:
        raise ReviewError(f"{len(missing)} sample row(s) have no verdict yet, e.g. {', '.join(missing[:5])}")
    not_ok = [r for r in sample if r["verdict"].strip().upper() != "OK"]
    if len(not_ok) / len(sample) > MAX_WRONG_SHARE:
        raise ReviewError(
            f"batch rejected: {len(not_ok)} of {len(sample)} sampled rows were not confirmed (limit {MAX_WRONG_SHARE:.0%}). "
            f"Examples: {', '.join(r['row_id'] for r in not_ok[:5])}. Fix the prompt or the source and re-ingest.")

    today = today or date.today()
    held, kept_claims, reviewed_claims = [], [], 0
    used_sources, used_entities = set(), set()
    for spec in batch["claims"]:
        claim = Claim(type=spec["type"], subject_id=spec["subject"], object_id=spec["object"], qualifiers=spec.get("qualifiers") or {})
        kept_evidence, any_reviewed = [], False
        for ev in spec["evidence"]:
            row = by_key.get((claim.id, ev["source"], quote_key(ev.get("quote"))))
            verdict = (row or {}).get("verdict", "").strip().upper()
            fit = (row or {}).get("local_fit", "").strip().upper()
            if verdict in ("WRONG", "UNSURE") or fit == "NO":
                held.append({"row_id": (row or {}).get("row_id", claim.id), "why": "verdict " + verdict if verdict in ("WRONG", "UNSURE") else "local_fit NO",
                             "comment": (row or {}).get("comment", ""), "claim": (row or {}).get("the_claim_in_words", "")})
                continue
            new_ev = {k: v for k, v in ev.items() if k != "candidate_id"}
            if verdict == "OK":
                name = (row.get("reviewer_name") or reviewer or "").strip()
                if not name:
                    raise ReviewError(f"row {row['row_id']}: OK needs a reviewer name (reviewer_name column or --reviewer)")
                new_ev["reviewer"], new_ev["reviewed_at"] = name, today.isoformat()
                any_reviewed = True
            kept_evidence.append(new_ev)
        if not kept_evidence:
            continue
        new_spec = {**{k: v for k, v in spec.items() if k != "evidence"}, "evidence": kept_evidence}
        if any_reviewed:
            new_spec["status"] = "reviewed"
            reviewed_claims += 1
        kept_claims.append(new_spec)
        used_entities.update((spec["subject"], spec["object"]))
        used_sources.update(ev["source"] for ev in kept_evidence)

    doc = {
        "sources": [s for s in batch["sources"] if s["id"] in used_sources],
        "entities": [e for e in batch["entities"] if e["id"] in used_entities],
        "claims": kept_claims,
    }
    header = f"Reviewed {today.isoformat()} from {batch_path.name} + {sheet_path.name}; sample {len(sample)} rows, {len(not_ok)} not confirmed."
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"# {header}\n\n" + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8", newline="\n")
    return AppliedReview(len(kept_claims), reviewed_claims, held, len(sample), len(not_ok))
