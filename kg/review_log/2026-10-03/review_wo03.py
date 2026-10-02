"""Reviewer decisions for batch WO03 (2026-10-03, reviewer: Claude, at the project owner's request). Input: batches/WO03.jsonl.
Output: batches/WO03.reviewed.jsonl. Every candidate is either dropped (DROP, with the reason) or kept with the edits below; nothing is
added that the source does not say."""

import json
import re

DROP = {
    "WO03-0003": "'Jawahar Soybean-2' is a transliteration with no code; cannot be tied to a variety name the page prints in Latin script",
    "WO03-0039": "KDS 726 here vs KSD 726 in the AICRP report: same variety (Phule Sangam), two spellings in two official sources; not asserted until reconciled",
    "WO03-0041": "recommended area lists several zones in one phrase ('central, eastern and north-eastern hill'); one zone claim would misstate it",
    "WO03-0049": "variety is named only in Devanagari; no Latin name to record",
    "WO03-0005": "'Moneta' is a transliteration of a Devanagari-only name",
    "WO03-0074": "pedigree text 'HI8498/PDW233/PDW291' is garbled in the PDF text (a line break inside it); cannot be verified verbatim",
    "WO03-0091": "the table row cited for MAUS 731 cannot be located in the page text",
}

# Quote corrections: the source's own characters. The model's reader showed table cells separated by ' | ', which the page text does not contain.
QUOTE_FIX = {
    "WO03-0001": "दुर्गा (JS 72-280) ... 1982 ... मध्य प्रदेश",
    "WO03-0099": None,  # handled below: 'DDW48 | 2021' -> 'DDW48 2021'
}

# Hindi-page rows: Latin code is the name; the Devanagari/common name goes in as a synonym or alias.
SOY = {
    "WO03-0002": dict(text="JS 72-44", synonyms=["Gaurawa"]),
    "WO03-0009": dict(text="JS 71"),
    "WO03-0012": dict(text="NRC 2", synonyms=["Ahilya-1"]),
    "WO03-0013": dict(text="NRC 12", synonyms=["Ahilya-2"]),
    "WO03-0014": dict(text="NRC 7", synonyms=["Ahilya-3"]),
    "WO03-0016": dict(text="MAUS 32", synonyms=["Prasad"]),
    "WO03-0017": dict(text="MAUS 47"),
    "WO03-0018": dict(text="Indira Soya 9", alias="इंदिरा सोया–9"),
    "WO03-0019": dict(text="NRC 37", synonyms=["Ahilya-4"]),
    "WO03-0020": dict(text="MAUS 61-2", entity_id="var:soybean:PRATISHTA"),
    "WO03-0022": dict(text="MAUS 81"),
    "WO03-0024": dict(text="DS 228", synonyms=["Phule Kalyani"]),
    "WO03-0034": dict(text="Raj Soya-24", alias="राज सोया-24"),
    "WO03-0035": dict(text="Raj Soya-18", alias="राज सोया-18"),
    "WO03-0036": dict(text="JS 20-98"),
    "WO03-0037": dict(text="MAUS 612", entity_id="var:soybean:MAUS612"),
    "WO03-0047": dict(text="AMS-MB-5-18", synonyms=["Suvarna Soya"]),
    "WO03-0053": dict(text="NRC 131"),
    "WO03-0055": dict(text="NRC 136"),
}

CHICKPEA = {
    "WO03-0058": dict(subject="Shubhra", obj="Central Zone"),
    "WO03-0059": dict(subject="IPCK 2004-29", synonyms=["Ujjawal"], obj="Central Zone"),
    "WO03-0060": dict(subject="IPC 2006-77", obj="Central Zone"),
}

SOWN = {"early": r"early sown", "timely": r"timely sown", "late": r"late sown"}


def split_common(text):
    """'HI 1634 (Pusa Ahilya)' -> ('HI 1634', ['Pusa Ahilya']); text without a trailing parenthesis is returned unchanged."""
    m = re.fullmatch(r"(.+?)\s*\(([^()]+)\)", text.strip())
    return (m.group(1).strip(), [m.group(2).strip()]) if m else (text.strip(), [])


out, dropped = [], []
for line in open("batches/WO03.jsonl", encoding="utf-8"):
    c = json.loads(line)
    cid = c["candidate_id"]
    if cid in DROP:
        dropped.append((cid, DROP[cid]))
        continue
    url = c["source"].get("url", "")
    if cid in QUOTE_FIX and QUOTE_FIX[cid]:
        c["quote"] = QUOTE_FIX[cid]
        c["subject"] = {"text": "JS 72-280", "type": "Variety", "synonyms": ["Durga"]}
    if " | " in c["quote"] and "icar-iipr.org.in" in url or cid == "WO03-0099":
        c["quote"] = c["quote"].replace(" | ", " ")
    if cid in SOY:
        d = SOY[cid]
        c["subject"] = {"text": d["text"], "type": "Variety", **({"synonyms": d["synonyms"]} if d.get("synonyms") else {}),
                        **({"alias_in_quote": d["alias"]} if d.get("alias") else {}), **({"entity_id": d["entity_id"]} if d.get("entity_id") else {})}
    if cid in CHICKPEA:
        d = CHICKPEA[cid]
        c["subject"] = {"text": d["subject"], "type": "Variety", **({"synonyms": d["synonyms"]} if d.get("synonyms") else {})}
        c["object"] = {"text": d["obj"], "type": "AgroZone"}
    if "iiwbr.org.in" in url and c["subject"]["type"] == "Variety" and cid not in SOY and cid not in CHICKPEA:
        name, common = split_common(c["subject"]["text"])
        c["subject"] = {"text": name, "type": "Variety", **({"synonyms": common} if common else {})}
        if c["claim_type"] == "VARIETY_RECOMMENDED_FOR_ZONE":
            q, quote = c["qualifiers"], c["quote"].lower()
            keep = {}
            if q.get("sowing") and re.search(SOWN[q["sowing"]], quote):
                keep["sowing"] = q["sowing"]
            if q.get("water_regime") == "irrigated" and "irrigated" in quote and "restricted" not in quote:
                keep["water_regime"] = "irrigated"
            if q.get("water_regime") == "restricted_irrigation" and "restricted" in quote:
                keep["water_regime"] = "restricted_irrigation"
            c["qualifiers"] = keep  # only what the quote itself states
    if cid == "WO03-0082":
        c["qualifiers"] = {"role": "selection_from"}  # the quote says "Selection from JS 80-21"
    # Latin names inside Hindi rows' DERIVED_FROM subjects
    if c["claim_type"] == "VARIETY_DERIVED_FROM" and "icar-nsri" in url:
        name, common = split_common(c["subject"]["text"])
        if cid == "WO03-0083":
            c["subject"] = {"text": "DS 228", "type": "Variety", "synonyms": ["Phule Kalyani"]}
        if cid == "WO03-0082":
            c["subject"] = {"text": "MAUS 32", "type": "Variety", "synonyms": ["Prasad"]}
    # wheat/Peninsular/Central parent entities: names as written
    if c["claim_type"] == "VARIETY_DERIVED_FROM" and "iiwbr.org.in" in url:
        pass
    out.append(c)

open("batches/WO03.reviewed.jsonl", "w", encoding="utf-8").write("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in out))
print(len(out), "kept;", len(dropped), "dropped by review")
