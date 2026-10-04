"""WO16: wheat varieties released / identified by the AICRP (Director's reports 2020-21, 2022-23, 2025-26): zone and production condition, and the rust reactions the release
table states in its 'special features' column. Rows are cut out of the report text by name; each candidate quotes the row. Central India only (Central and Peninsular zones and the MP / Gujarat
state releases) plus the Indore-bred NWPZ releases that were already in the KB. Output: batches/WO16.jsonl (then kg ingest-candidates)."""

import json
import re

import curator.model  # noqa: F401
from curator.graph.quote_audit import fetch_url_text, normalise

BASE = "http://www.aicrpwheatbarleyicar.in/wp-content/uploads/"
DOCS = {
    "2020-21": dict(url=BASE + "2021/10/DIRECTOR-REPORT-2021-Corrected_compressed.pdf", slug="aicrp_wb_director_report_2020_21", year=2021,
                    title="AICRP on Wheat and Barley: Director's Report 2020-21", start="wheat varieties released by the cvrc during 2020-21 variety area", end="registration of genetic stocks"),
    "2022-23": dict(url=BASE + "2023/08/Directors-Report-2022-23.pdf", slug="aicrp_wb_director_report_2022_23", year=2023,
                    title="AICRP on Wheat and Barley: Director's Report 2022-23", start="hd3406 icar-iari", end="registration of new genetic stocks"),
    "2025-26": dict(url=BASE + "2026/09/Director-report-2026.pdf", slug="aicrp_wb_director_report_2025_26", year=2026,
                    title="AICRP on Wheat and Barley: Director's Report 2025-26", start="wheat varieties identiied during 2025-26", end="molecular marker proiling"),
}
LEAF, STEM, STRIPE = ("leaf rust", ["brown rust", "leaf rust", "brown", "leaf"]), ("stem rust", ["black rust", "stem rust", "black", "stem"]), ("stripe rust", ["yellow rust", "stripe rust", "yellow"])
# (report, row-start text as printed, name, synonyms, developer, zone codes, sowing, water, release year, [(disease, class, phrase proving it)])
ROWS = [
    ("2020-21", "cg 1029", "CG 1029", ["Kanishka"], None, ["CZ"], "late", "irrigated", 2021, []),
    ("2020-21", "hi 1634", "HI 1634", ["Pusa Ahilya"], None, ["CZ"], "late", "irrigated", 2021, [(LEAF, "R", "resistance to brown & black rusts"), (STEM, "R", "resistance to brown & black rusts")]),
    ("2020-21", "hi 1633", "HI 1633", ["Pusa Vani"], None, ["PZ"], "late", "irrigated", 2021, []),
    ("2020-21", "nidw 1149 (d)", "NIDW 1149", [], None, ["PZ"], "timely", "restricted_irrigation", 2021, [(LEAF, "R", "resistance to brown and yellow rusts"), (STRIPE, "R", "resistance to brown and yellow rusts")]),
    ("2020-21", "ddw 48 (d)", "DDW 48", [], None, ["PZ"], "timely", "irrigated", 2021, []),
    ("2020-21", "macs4058 (d)", "MACS 4058", [], None, ["PZ"], "timely", "restricted_irrigation", 2021, [(LEAF, "R", "resistant to leaf & stem rusts"), (STEM, "R", "resistant to leaf & stem rusts")]),
    ("2022-23", "hi 1650", "HI 1650", ["Pusa Ojaswi"], "ICAR-IARI Regional Station, Indore", ["CZ"], "timely", "irrigated", 2022, [(LEAF, "R", "highly resistant to leaf and"), (STEM, "R", "stem rust, high zinc")]),
    ("2022-23", "cg 1036", "CG 1036", ["Vidhya"], "IGKV, Bilaspur", ["CZ"], "timely", "restricted_irrigation", 2022, [(LEAF, "R", "resistance to leaf and stem rust"), (STEM, "R", "resistance to leaf and stem rust")]),
    ("2022-23", "hi1655", "HI 1655", ["Pusa Harsha"], "ICAR-IARI Regional Station, Indore", ["CZ"], "timely", "restricted_irrigation", 2022, [(LEAF, "R", "resistance to leaf and stem rust"), (STEM, "R", "resistance to leaf and stem rust")]),
    ("2022-23", "hi 8830 (pusa kir)", "HI 8830", ["Pusa Kir"], "ICAR-IARI Regional Station, Indore", ["CZ"], "timely", "restricted_irrigation", 2022, [(LEAF, "R", "resistance to leaf and stem"), (STEM, "R", "rust, good amount of yellow pigment")]),
    ("2022-23", "ddw55", "DDW 55", ["Karan Manjari"], "ICAR-IIWBR, Karnal", ["CZ"], "timely", "restricted_irrigation", 2022, []),
    ("2022-23", "hi8826", "HI 8826", ["Pusa Poshk"], "ICAR-IARI Regional Station, Indore", ["PZ"], "timely", "irrigated", 2022, [(LEAF, "R", "resistance to leaf and stem"), (STEM, "R", "rust, hard grains")]),
    ("2022-23", "macs4100", "MACS 4100", ["MACS Jejuri"], "ARI, Pune", ["PZ"], "timely", "irrigated", 2022, [(LEAF, "R", "resistance to leaf rust")]),
    ("2022-23", "hi 1653", "HI 1653", ["Pusa Jagra"], "ICAR-IARI Regional Station, Indore", ["NWPZ"], "timely", "restricted_irrigation", 2022, [(LEAF, "R", "resistant to wheat blast")]),
    ("2022-23", "hi 1654", "HI 1654", ["Pusa Adi"], "ICAR-IARI Regional Station, Indore", ["NWPZ"], "timely", "restricted_irrigation", 2022, [(LEAF, "MR", "tolerant to wheat blast and")]),
    ("2025-26", "jw 1399", "JW 1399", ["MP 1399"], "Powarkheda", ["CZ"], "early", "irrigated", None, []),
    ("2025-26", "dbw 426", "DBW 426", ["Karan Devika"], "ICAR-IIWBR, Karnal", ["PZ"], "late", "irrigated", None, [(LEAF, "R", "resistant to brown and"), (STEM, "R", "black rust; bio-fortiied")]),
    ("2025-26", "pbw 906", "PBW 906", [], "PAU, Ludhiana", ["CZ"], "early", "irrigated", None, [(LEAF, "R", "resistant to brown rust"), (STEM, "MR", "moderately resistant to black rust")]),
    ("2025-26", "gw 555", "GW 555", ["Sorath Amber"], "Wheat Research Station, JAU, Junagadh", ["CZ"], "timely", "irrigated", None, [(STEM, "R", "high level of resistance to black rust (aci: 6.8)"), (LEAF, "R", "brown rust (aci: 3.4)")]),
    ("2025-26", "gw 556", "GW 556", ["Sorath Ushma"], "Wheat Research Station, JAU, Junagadh", ["CZ"], "late", "irrigated", None, [(LEAF, "R", "high level of resistance against brown rust (aci: 4.0)"), (STEM, "R", "black rust (aci: 8.9)")]),
    ("2025-26", "niaw4267", "NIAW 4267", ["Phule Sampanna"], "MPKV, Agricultural Research Station, Niphad", ["PZ"], "timely", "restricted_irrigation", None, [(LEAF, "R", "highly resistant to brown rust")]),
    ("2025-26", "wsm 138", "WSM 138", [], "Wheat Research Unit, PDKV, Akola", ["CZ"], "late", "irrigated", None, [(LEAF, "R", "highly resistant to brown and black rust"), (STEM, "R", "highly resistant to brown and black rust")]),
    ("2025-26", "macs 6837", "MACS 6837", ["MACS Vindhya"], "ARI, Pune", ["CZ"], "timely", "irrigated", None, [(STEM, "R", "resistant to black and brown rusts"), (LEAF, "R", "resistant to black and brown rusts")]),
    ("2025-26", "macs 6830", "MACS 6830", ["MACS Shivneri"], "ARI, Pune", ["PZ"], "late", "irrigated", None, [(STEM, "R", "highly resistant to black and brown rusts"), (LEAF, "R", "highly resistant to black and brown rusts")]),
    ("2025-26", "hi 1683", "HI 1683", ["Pusa Samrat"], "ICAR-IARI Regional Station, Indore", ["CZ"], "timely", "irrigated", None, [(STEM, "R", "resistance against black and brown rusts"), (LEAF, "R", "resistance against black and brown rusts")]),
    ("2025-26", "hi 1687", "HI 1687", ["Pusa Atal"], "ICAR-IARI Regional Station, Indore", ["PZ"], "late", "irrigated", None, [(STEM, "R", "resistant to black and brown rust"), (LEAF, "R", "resistant to black and brown rust")]),
    ("2025-26", "dbw 425", "DBW 425", [], "ICAR-IIWBR, Karnal", ["CZ"], "late", "irrigated", None, [(STEM, "R", "resistance to black and brown rusts"), (LEAF, "R", "resistance to black and brown rusts")]),
    ("2025-26", "dbw 445", "DBW 445", ["Karan Gourav"], "ICAR-IIWBR, Karnal", ["CZ"], "early", "irrigated", None, [(STEM, "R", "highly resistant to black and brown rusts"), (LEAF, "R", "highly resistant to black and brown rusts")]),
    ("2025-26", "cg 1047", "CG 1047", ["Chhattisgarh Trombay Kumud"], "IGKV, Bilaspur and BARC, Trombay", ["PZ"], "timely", "restricted_irrigation", None, []),
    ("2025-26", "hd 3463", "HD 3463", [], "ICAR-IARI, New Delhi", ["CZ"], "early", "irrigated", None, [(STEM, "R", "highly resistant to black and brown rust"), (LEAF, "R", "highly resistant to black and brown rust")]),
    ("2025-26", "jw1398", "JW 1398", ["MP 1398"], "Powarkheda", ["CZ"], "timely", "restricted_irrigation", None, []),
    ("2025-26", "uas 484", "UAS 484", [], "UAS, Dharwad", ["CZ"], "timely", "restricted_irrigation", None, [(STEM, "R", "resistance to black and brown rusts"), (LEAF, "R", "resistance to black and brown rusts")]),
    ("2025-26", "hi 8849", "HI 8849", ["Pusa Mangal"], "ICAR-IARI Regional Station, Indore", ["PZ"], "timely", "irrigated", None, [(STEM, "R", "high level of resistance against black and brown rust"), (LEAF, "R", "high level of resistance against black and brown rust")]),
    ("2025-26", "hi 8851", "HI 8851", ["Pusa Prachand"], "ICAR-IARI Regional Station, Indore", ["CZ"], "timely", "restricted_irrigation", None, [(LEAF, "R", "resistant to brown and black rust"), (STEM, "R", "resistant to brown and black rust")]),
    ("2025-26", "hi 8850", "HI 8850", ["Pusa Poshan Shakti"], "ICAR-IARI Regional Station, Indore", ["CZ"], "timely", "irrigated", None, [(LEAF, "R", "resistance to brown and black rust"), (STEM, "R", "resistance to brown and black rust")]),
    ("2025-26", "macs 4135", "MACS 4135", ["MACS Mahabal"], "ARI, Pune", ["CZ", "PZ"], "timely", "irrigated", None, []),
]


FAILED = []


def has_in_order(phrase: str, window: str) -> bool:
    """The row's columns are interleaved in the PDF text ('highly resistant to unit, pdkv, sown brown and black rust'), so a phrase counts when its words occur in order."""
    words = iter(re.findall(r"[a-z0-9().:%&-]+", window))
    return all(w in words for w in re.findall(r"[a-z0-9().:%&-]+", phrase))


def main():
    texts, regions = {}, {}
    for season, d in DOCS.items():
        texts[season] = normalise(fetch_url_text(d["url"]) or "")
        assert texts[season], season
        a = texts[season].index(d["start"])
        b = texts[season].index(d["end"], a)
        regions[season] = texts[season][a:b]
    out, n = [], 0
    for idx, (season, start, name, syn, dev, zones, sowing, water, year, reactions) in enumerate(ROWS):
        region = regions[season]
        s = -1
        for m in re.finditer(re.escape(start), region):     # the report repeats the narrative before the table: take the occurrence that is the table row
            window = region[m.start():m.start() + 420]
            if all(has_in_order(ph, window) for _, _, ph in reactions) and re.search(r"(?:cz|pz|nwpz|nepz|nhz)", window[:140]):
                s = m.start()
                break
        if s < 0:
            FAILED.append((season, start, [ph for _, _, ph in reactions]))
            continue
        # the row ends where the next row of the same report starts (or after 420 characters)
        nxt = [region.find(r[1], s + len(start)) for r in ROWS[idx + 1:] if r[0] == season]
        nxt = [x for x in nxt if x > s]
        e = min(nxt + [s + 420]) if nxt else s + 420
        row = region[s:e].strip()
        row_parts = [p.strip() for p in re.split(r"director.?s report \(?20\d\d[-\d]*\)? ?\d* ?(?:director.?s report \(?20\d\d[-\d]*\)? ?\d*)?", row) if p.strip()]
        quote = " ... ".join(row_parts)
        d = DOCS[season]
        source = {"kind": "official_document", "url": d["url"], "doc_slug": d["slug"], "title": d["title"], "publisher": "ICAR-Indian Institute of Wheat and Barley Research, Karnal (AICRP on Wheat and Barley)", "year": d["year"]}
        props = {k: v for k, v in {"release_year": year, "releasing_institute": dev}.items() if v}
        subj = {"text": name, "type": "Variety", "synonyms": syn, **({"props": props} if props else {}), "alias_in_quote": start.split(" (")[0]}
        for z in zones:
            n += 1
            out.append({"candidate_id": f"WO16-{n:04d}", "producer": "claude-from-report-text", "batch_id": "WO16-2026-10-04", "crop": "wheat", "claim_type": "VARIETY_RECOMMENDED_FOR_ZONE",
                        "subject": subj, "object": {"text": z, "type": "AgroZone", "alias_in_quote": z.lower()}, "qualifiers": {"season": "rabi", "sowing": sowing, "water_regime": water},
                        "source": source, "locator": f"Release / identification table {season}", "quote": quote, "evidence_basis": "official_document"})
        for (disease, aliases), reaction, phrase in reactions:
            assert has_in_order(phrase, row), (name, phrase, row)
            alias = next((a for a in aliases if re.search(r'(?<![a-z])' + re.escape(a) + r'(?![a-z])', row)), None)  # a literal alias is needed for the verifier; interleaved rows fall back to the short forms
            assert alias, (name, disease, row)
            n += 1
            out.append({"candidate_id": f"WO16-{n:04d}", "producer": "claude-from-report-text", "batch_id": "WO16-2026-10-04", "crop": "wheat", "claim_type": "VARIETY_REACTION",
                        "subject": subj, "object": {"text": disease, "type": "Disease", "alias_in_quote": alias}, "qualifiers": {"reaction": reaction, "stage": "unspecified", "season": season},
                        "source": source, "locator": f"Release / identification table {season}, special features", "quote": quote, "evidence_basis": "official_document"})
    open("batches/WO16.jsonl", "w", encoding="utf-8").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
    print("ROWS NOT LOCATED:", FAILED)
    print(len(out), "candidates;", sum(1 for r in out if r["claim_type"] == "VARIETY_REACTION"), "reactions")


if __name__ == "__main__":
    main()
