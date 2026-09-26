# Legacy v1 literature pipeline (archived 2026-09-26)

`fetch_papers.py` → `paper_extractor.py` → `approve_extractions.py`, plus `validator.py`
(consumed only by these) and their test. **Do not resurrect this chain.** It is the direct cause
of the D1/D2 incident in RESEARCH_ROADMAP.md §2.2: `fetch_papers.py`'s `CURATED_PAPERS` list had
PMIDs that were never checked against the real registry (11 of 20 "wheat" papers were unrelated —
sports medicine, psychiatry, neural stem cells — with a fabricated `TITLE:`/`NOTE:` header sent to
the LLM along with the real body), `paper_extractor.py` never captured a verbatim quote so the
resulting records couldn't be checked against the source text, and every record that reached
`data/review_queue.json` traced back to a paper that had nothing to do with its claimed content.

It also targets Neo4j (`curator/db.py`), which is not the data store the current system uses —
`agrihub kg build`/`load`/`promote` (Postgres, `curator/model/*`, `kg/curated/*.yaml`) is the only
live path for facts entering this knowledge base.

Phase 5 v2 (`curator/lit/`, `curator/llm/`, `curator/extract/`) replaces this: every source is
verified against Europe PMC/Crossref before use, every LLM-produced claim requires a verbatim
quote checked against the actual fetched text (`curator/extract/ground.py`), and output is a draft
for human review, not an auto-write into the graph. See `RESEARCH_ROADMAP.md` §5–6 and `PHASES.md`
for the full record of this decision.
