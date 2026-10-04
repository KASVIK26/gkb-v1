# Review log: chickpea last try — dry root rot and rust (2026-10-04)

**Reviewer: Claude (an AI), acting for the project owner.** No reviewer name or `status: reviewed`; `llm:` evidence stays discounted.

## Why "last try"
The 2026-10-03 open-literature sweep found nothing for chickpea dry root rot, collar rot or rust. On a second pass with title-focused web search (not just Europe PMC's own search), three papers turned up that
Europe PMC does not index with a PMID and does not mark open-access, so the earlier sweep's `OPEN_ACCESS:y` filter had hidden them entirely. Their DOIs resolve on Crossref, and the publisher landing page exposes
a full abstract (not the full paper), which is enough for a cited, verbatim-quoted claim — the same "abstract only, not full text" situation as several review-table claims already in the KB.

## Added (7 claims, 3 papers, chickpea dry root rot and rust only — collar rot still has nothing)
- **qDRR-8** (Talekar et al. 2021, *Euphytica*, doi:10.1007/s10681-021-02854-4): a QTL on CaLG08, PVE 6.70%, LOD 3.34, from 182 F9 RILs (BG 212 x ICCV 08305) screened against the Rb 6 isolate of *R. bataticola* at ICRISAT, 2016-2017.
- **A second dry-root-rot locus** (Talekar et al. 2017, *Plant Breeding*, doi:10.1111/pbr.12448): monogenic inheritance in 129 F2:3 progeny of L550 x PG06102; two SSR markers, ICCM0299 and ICCM0120b, co-segregating with
  resistance. The locus has no formal name in the paper, so it is entered as an informally-named QTL (`qDRR-L550xPG06102`) rather than invented as a gene symbol.
- **Uca1** (Madrid et al. 2008, *European Journal of Plant Pathology*, doi:10.1007/s10658-007-9240-7): a single dominant gene hypothesised for adult-plant rust resistance in an interspecific cross (*C. arietinum*
  ILC72 x *C. reticulatum* Cr5-10); the same locus's QTL explains 31% of seedling disease severity and 81% of adult AUDPC. Flanked by SSR markers TA18 and TA180 (3.9 cM apart); resistance_type left `unknown` because the
  paper itself calls it dominant monogenic in adults but QTL-like in both stages (not cleanly ASR or APR).

## What this does not fix
- **Collar rot**: still nothing. The search returned only germplasm screening (resistant/moderately-resistant lists, already the kind of claim the KB holds) and one unrelated QTL paper (*Sclerotinia* stem rot, a
  different pathogen, not Sclerotium rolfsii) — not used.
- **Only abstracts were read**, not the full papers: tables of individual marker positions, LOD profiles or additional loci inside these papers (if any) are not captured. If full text becomes reachable, re-extracting
  from it would very likely add more.
- Both dry-root-rot papers use ICRISAT breeding material (BG 212, ICCV 08305, L550, PG06102) that is not yet in the KB's variety list; no variety-level claim was created from them.
