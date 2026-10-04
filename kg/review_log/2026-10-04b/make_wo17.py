"""WO17: soybean variety reactions that the AICRP on Soybean annual reports (ICAR-NSRI Indore, 2017-18 to 2024-25) state in their plant-pathology narrative:
"entries X, Y showed HR / AR / MR reaction to <disease> at <centre>". Abbreviations as the reports use them: HR highly resistant, AR absolutely resistant (no infection), MR moderately
resistant; CR charcoal rot, PB(CT) pod blight (Colletotrichum truncatum = anthracnose), FLS frogeye leaf spot. Only sentences that name the disease, only varieties already in the KB.
Each candidate quotes the report sentence. Output: batches/WO17.jsonl (then kg ingest-candidates)."""

import json
import pathlib
import re

import curator.model  # noqa: F401
from curator.graph.quote_audit import fetch_url_text, normalise

CACHE = "C:/Users/vikas/AppData/Local/Temp/claude/C--Users-vikas-gkb-v1/a204d952-4466-4fb7-8674-7c9cb736e0f6/scratchpad/"  # normalised text cached by an earlier fetch (same fetch_url_text + normalise)
B1 = "https://icar-nsri.res.in/newwebsitehindi/pdfdoc/"
B2 = "https://icar-nsri.res.in/pdfdoc/"
DOCS = {
    "2017-18": (B1 + "AicrpsAR2017-18.pdf", "aicrps_annual_report_2017_18", 2018),
    "2018-19": (B1 + "AicrpsAR2018-19.pdf", "aicrps_annual_report_2018_19", 2019),
    "2019-20": (B1 + "AicrpsAR2019-20.pdf", "aicrps_annual_report_2019_20", 2020),
    "2020-21": (B1 + "AicrpsAR2020-21.pdf", "aicrps_annual_report_2020_21", 2021),
    "2022-23": (B2 + "AicrpsAR2022_23.pdf", "aicrps_annual_report_2022_23", 2023),
    "2023-24": (B2 + "AicrpsAR2023-24.pdf", "aicrps_annual_report_2023_24", 2024),
    "2024-25": (B2 + "AicrpsAR2024-25.pdf", "aicrps_annual_report_2024_25", 2025),
}
DISEASE = {"rust": ("soybean rust", "rust"), "cr": ("charcoal rot", "cr"), "fls": ("frogeye leaf spot", "fls"), "pb": ("anthracnose (pod blight)", "pb(ct)")}
# (report, sentence start as printed, [(variety, literal name in the sentence, reaction)], disease key)
ROWS = [
    ("2017-18", "the variety dsb 21 maintained hr reaction to rust for the last eight years", [("DSb 21", "dsb 21", "R")], "rust"),
    ("2018-19", "the variety dsb 21 maintained hr reaction to rust for the last nine years", [("DSb 21", "dsb 21", "R")], "rust"),
    ("2019-20", "the entries dsb 21, dsb 23 & dsb 28 maintained their hr reaction to rust at their 8 th year", [("DSb 21", "dsb 21", "R"), ("DSb 23", "dsb 23", "R")], "rust"),
    ("2020-21", "the entries dsb 21, and dsb 23 , dsb 28 maintained their hr reaction t o rust at their 9 th year", [("DSb 21", "dsb 21", "R"), ("DSb 23", "dsb 23", "R")], "rust"),
    ("2023-24", "for rust, all ivt(n) entries except vls99 at k.digraj showed hs to s reaction", [("DSb 21", "dsb21", "R"), ("MACS 1188", "macs 1188", "MR")], "rust"),
    ("2019-20", "at jabalpur, the entries js 20-34, js 20-98, js 20-36 and nrc 125 showed hr reaction t o cr", [("JS 20-34", "js 20-34", "R"), ("JS 20-98", "js 20-98", "R")], "cr"),
    ("2024-25", "js 20-98, js 20-20 showed hr reaction for cr disease at jabalpur in 9th year of testing", [("JS 20-98", "js 20-98", "R")], "cr"),
    ("2020-21", "in cz, three entries js 21 -72, nrc 142, nrc 150 showed hr reaction towards cr at jabalpur", [("JS 21-72", "js 21 -72", "R"), ("NRC 150", "nrc 150", "R")], "cr"),
    ("2018-19", "in cz at jabalpur, the entries ams 100 -39.kds 992,nrc 130,ps 1613 and vls 94 showed ar reaction to cr", [("AMS 100-39", "ams 100 -39", "R"), ("NRC 130", "nrc 130", "R")], "cr"),
    ("2017-18", "in cz at jabalpur, the entries macs 1520,nrc 125 and rsc 10 -52 showed ar reaction to cr", [("MACS 1520", "macs 1520", "R")], "cr"),
    ("2022-23", "addition ally, five entries (js 22-12, js 22-18, nrc 181, js 23-03 and js 23-09) showed hr reaction against cr", [("NRC 181", "nrc 181", "R")], "cr"),
    ("2017-18", "in nhz, at palampur js 20-116 recorded ar reaction and ps 1572 showed hr reaction for fls", [("JS 20-116", "js 20-116", "R")], "fls"),
    ("2025-26", None, [], "fls"),
    ("2024-25", "himso 1685 & js 20-116 showed mr reaction to fls at almora in 8 th year of testing", [("JS 20-116", "js 20-116", "MR")], "fls"),
    ("2023-24", "for fls disease, ivt(n) entries nrc 266, nrc 138, ds 1480, nrc 150, js 25 - 06, maus 787, nrc 265, js 20-34", [("NRC 150", "nrc 150", "R"), ("JS 20-34", "js 20-34", "R")], "fls"),
    ("2018-19", "in nhz, at palampur two entries (nrc 147 and vls 94 ) showed ar reaction to fls while entries ( rsc 11-07 and sl 1123 ) showed hr reaction", [("RSC 11-07", "rsc 11-07", "R")], "fls"),
    ("2017-18", "at palampur, cat 1328, cat 1878 and ps 1347 entries were ar and 16 hr to fls", [("PS 1347", "ps 1347", "R")], "fls"),
    ("2017-18", "in nehz, at medziphema two entries(nrc 126 and rvs 2009 -9) showed ar reaction to pb(ct) while six entries(ams -mb5-18", [("AMS-MB-5-18", "ams -mb5-18", "R"), ("MACS 1520", "macs 1520", "R"), ("NRC 127", "nrc 127", "R")], "pb"),
    ("2018-19", "in nehz, at medziphema two entri es(ps 1611 and rsc 11 -03) showed ar reaction to pb(ct) while five entries(ams-2014-1", [("NRC 128", "nrc 128", "R")], "pb"),
]
ROWS = [r for r in ROWS if r[1]]


def sentence_at(text: str, start: str) -> str:
    i = text.find(start)
    assert i >= 0, start
    j = text.find(". ", i + len(start))
    j = j if 0 < j - i < 520 else i + 520
    return text[i:j + (1 if text[j:j + 1] == "." else 0)].strip()


def main():
    texts = {}
    for season, (url, slug, year) in DOCS.items():
        cache = pathlib.Path(CACHE + "s" + season[2:4] + season[5:7] + ".txt")
        texts[season] = cache.read_text(encoding="utf-8") if cache.exists() else normalise(fetch_url_text(url) or "")
        assert texts[season], season
    out, n = [], 0
    for season, start, subjects, dkey in ROWS:
        text = texts[season]
        quote = sentence_at(text, start)
        url, slug, year = DOCS[season]
        source = {"kind": "official_document", "url": url, "doc_slug": slug, "title": f"AICRP on Soybean annual report {season}", "publisher": "ICAR-Indian Institute of Soybean Research, Indore (AICRP on Soybean)", "year": year}
        dname, dalias = DISEASE[dkey]
        assert dalias in quote or (dalias == "pb(ct)" and "pb(ct)" in quote.replace(" ", "")), (season, dkey, quote)
        for variety, literal, reaction in subjects:
            assert literal.replace(" ", "") in quote.replace(" ", ""), (variety, quote)
            n += 1
            out.append({"candidate_id": f"WO17-{n:04d}", "producer": "claude-from-report-text", "batch_id": "WO17-2026-10-04", "crop": "soybean", "claim_type": "VARIETY_REACTION",
                        "subject": {"text": variety, "type": "Variety", "alias_in_quote": literal}, "object": {"text": dname, "type": "Disease", "alias_in_quote": dalias},
                        "qualifiers": {"reaction": reaction, "stage": "unspecified"}, "source": source, "locator": f"Plant pathology, AICRP soybean {season}", "quote": quote,
                        "evidence_basis": "official_document"})
    open("batches/WO17.jsonl", "w", encoding="utf-8").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out))
    print(len(out), "candidates")


if __name__ == "__main__":
    main()
