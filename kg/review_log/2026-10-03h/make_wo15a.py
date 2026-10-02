"""WO15a: the seven Asian soybean rust resistance genes mapped in pmid:37375888, as gene -> soybean rust claims (quote: the paper's abstract sentence)."""
import json
Q = ("To facilitate the development of resistant varieties using gene pyramiding, DNA markers closely linked to seven resistance genes, namely, Rpp1, Rpp1-b, Rpp2, Rpp3, Rpp4, Rpp5, and Rpp6, were identified. ")
HEAD = "Asian soybean rust (ASR), caused by Phakopsora pachyrhizi, is one of the most serious soybean (Glycine max) diseases in tropical and subtropical regions."
rows = []
for i, g in enumerate(["Rpp1", "Rpp1-b", "Rpp2", "Rpp3", "Rpp4", "Rpp5", "Rpp6"], 1):
    rows.append({"candidate_id": f"WO15a-{i:04d}", "producer": "claude-from-paper-text", "batch_id": "WO15a-2026-10-03", "crop": "soybean", "claim_type": "GENE_CONFERS_RESISTANCE",
                 "subject": {"text": g, "type": "Gene", "props": {"symbol": g}}, "object": {"text": "soybean rust", "type": "Disease", "alias_in_quote": "soybean rust"},
                 "qualifiers": {"resistance_type": "unknown"},
                 "source": {"kind": "publication", "pmid": "37375888", "title": "Genetic Mapping of Seven Kinds of Locus for Resistance to Asian Soybean Rust"},
                 "locator": "Abstract", "quote": f"{HEAD} ... {Q.strip()}", "evidence_basis": "primary_qtl"})
open("batches/WO15a.jsonl", "w", encoding="utf-8").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
