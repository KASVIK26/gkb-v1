# kg/curated/ — hand-curated knowledge

One YAML file per topic/dataset. `agrihub kg build` merges every file here with the reference
entities auto-generated from `config/vocab/diseases.yaml` (Crop, Disease, Pathogen — never
hand-write those, they're regenerated every build) into one release.

## File format

```yaml
sources:
  - id: pmid:12345678       # pmid:<digits> | doi:<doi> | cat:<slug> | trial:<slug> | doc:<slug> | vocab:<slug>
    type: publication        # publication | dataset | trial_report | catalogue | official_document | curated_vocab
    title: "..."
    year: 2020
    venue: Journal name
    url: https://...
    verified: true            # publication sources MUST be true — see "Verifying a source" below

entities:
  - id: gene:wheat:Sr45       # see curator/normalize/ids.py for the ID grammar
    type: Gene
    name: Sr45
    crop: wheat
    synonyms: []
    props: {symbol: Sr45, chromosome: 1DS}   # validated against curator/model/entities.py

claims:
  - type: GENE_CONFERS_RESISTANCE            # see curator/model/enums.py CLAIM_SIGNATURE
    subject: gene:wheat:Sr45
    object: dis:wheat:stem_rust
    qualifiers: {resistance_type: ASR}       # validated per claim type, curator/model/claims.py
    status: unreviewed                        # unreviewed | reviewed | predicted | rejected
    evidence:                                 # every claim needs at least one
      - source: pmid:12345678
        method: cloned_validated              # curator/model/enums.py EvidenceMethod
        locator: abstract                     # section/table/page — be honest about what you actually read
        quote: "..."                          # required if extractor starts with "llm:"
        extractor: manual:curator             # llm:<model>@<prompt_v> | parser:<name>@<v> | manual:<who>
```

## Verifying a source

"Verified" means you checked the metadata against the actual registry, not memory or a plausible-looking
citation — this is the exact failure mode that put fabricated papers in the old `data/review_queue.json`
(RESEARCH_ROADMAP.md §2.2 D1/D2). In practice: look the PMID up on
[Europe PMC](https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:<pmid>&format=json) or
PubMed and confirm the title matches before setting `verified: true`. Phase 5 automates this; until then, do
it by hand and don't skip it.

## Running it

```powershell
.\.venv\Scripts\python.exe -m curator.cli kg build          # validate only, no database
.\.venv\Scripts\python.exe -m curator.cli kg load --release 2026_10_1   # creates schema kg_2026_10_1
```

`kg load` reads `DATABASE_URL_DIRECT` from the environment (the session-pooler string, not the transaction
pooler — see `.env.example`) unless you pass `--database-url`. It refuses to overwrite an existing release
schema; releases are immutable once loaded (TECH_STACK.md ADR-7).
