"""WO13a: gene -> disease links for the rust genes that varieties carry in the KB but that had no GENE_CONFERS_RESISTANCE claim.
The sentences are the AICRP Crop Protection reports' own: "<n> stem rust resistance genes (Sr2, ...) were characterized", "<n> Yr genes viz. ...
contributed to yellow rust resistance", "<n> Lr genes ...; Lr13 was the most commonly postulated leaf rust resistance gene". Quotes are copied from the
report text with its own capitalisation; the verifier re-checks them."""

import json
import re

from curator.graph.quote_audit import fetch_url_text

REPORTS = {
    "2021-22": dict(url="https://www.aicrpwheatbarleyicar.in/wp-content/uploads/2022/08/Crop-Protection-Report-2021-22_Final-18.08.2022_compressed.pdf",
                    slug="aicrp_crop_protection_2021_22", title="AICRP-W&B Progress Report Crop Protection 2021-22", year=2022),
    "2022-23": dict(url="https://www.aicrpwheatbarleyicar.in/wp-content/uploads/2023/08/Crop-Protection-Report2022-23_compressed.pdf",
                    slug="aicrp_crop_protection_2022_23", title="AICRP-W&B Progress Report Crop Protection 2022-23", year=2023),
}
# (report, regex that finds the sentence(s) in the report's raw text, genes the sentence lists, disease text, alias in quote)
SENTENCES = [
    ("2021-22", r"fourteen stem rust resistance genes\s*\(\s*Sr2.{0,140}?were characterized in 133 entries", "Sr2 Sr5 Sr7a Sr7b Sr8a Sr8b Sr9b Sr9e Sr11 Sr13 Sr24 Sr28 Sr30 Sr31", "stem rust", "stem rust"),
    ("2022-23", r"thirteen stem rust resistance genes\s*\(\s*Sr2.{0,140}?were characterized in\s*93\s*AVT lines", "Sr2 Sr5 Sr7b Sr8a Sr8b Sr9b Sr9e Sr11 Sr13 Sr24 Sr28 Sr30 Sr31", "stem rust", "stem rust"),
    ("2022-23", r"three\s*Yr genes viz\.\s*Yr2, Yr9, and Yra contributed to yellow rust resistance in Indian wheat material", "Yr2 Yr9 Yra", "stripe rust", "yellow rust"),
    ("2021-22", r"four Yr genes viz\.\s*Yr2, Yr9, Yra and Yr18 contributed to yellow rust resistance in Indian wheat material", "Yr2 Yr9 Yra", "stripe rust", "yellow rust"),
    ("2022-23", r"eight Lr genes viz\.\s*Lr1, Lr3, Lr10, Lr13, Lr23, Lr24, Lr26, and Lr28\s*were characterized in 100 AVT lines\.\s*Lr13 was the most commonly occurring leaf rust resistance",
     "Lr1 Lr3 Lr10 Lr13 Lr23 Lr24 Lr26 Lr28", "leaf rust", "leaf rust"),
    ("2021-22", r"eight Lr genes Lr1, Lr3, Lr10, Lr13, Lr23, Lr24, Lr26, and Lr34 were characterized in 113 entries\.\s*Lr13 was the most commonly postulated leaf rust resistance gene",
     "Lr1 Lr3 Lr10 Lr13 Lr23 Lr24 Lr26", "leaf rust", "leaf rust"),
]


def main():
    texts = {k: re.sub(r"\s+", " ", fetch_url_text(v["url"]) or "") for k, v in REPORTS.items()}
    rows, n = [], 0
    for year, pattern, genes, disease, alias in SENTENCES:
        m = re.search(pattern, texts[year], flags=re.I | re.S)
        assert m, (year, pattern[:60])
        quote = m.group(0)
        rep = REPORTS[year]
        for gene in genes.split():
            n += 1
            rows.append({
                "candidate_id": f"WO13a-{n:04d}", "producer": "claude-from-report-text", "batch_id": "WO13a-2026-10-03", "crop": "wheat",
                "claim_type": "GENE_CONFERS_RESISTANCE",
                "subject": {"text": gene, "type": "Gene"}, "object": {"text": disease, "type": "Disease", "alias_in_quote": alias},
                "qualifiers": {"resistance_type": "unknown"},
                "source": {"kind": "official_document", "url": rep["url"], "doc_slug": rep["slug"], "title": rep["title"], "publisher":
                           "ICAR-Indian Institute of Wheat and Barley Research, Karnal (AICRP on Wheat and Barley)", "year": rep["year"]},
                "locator": f"Programme 2, rust gene postulation ({year})", "quote": quote, "evidence_basis": "review_or_secondary",
            })
    open("batches/WO13a.jsonl", "w", encoding="utf-8").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    print(len(rows), "candidates")


if __name__ == "__main__":
    main()
