# Research prompts: how to use them

The plan is in [../CLAIMS_3000_PLAN.md](../CLAIMS_3000_PLAN.md). This folder holds the machinery.

| file | what it is |
|---|---|
| `_shared_spec.md` | the rules, output format, claim-type table and quality bar every prompt includes (template with `{{...}}` slots) |
| `_preamble_chatgpt.md`, `_preamble_grok.md` | how to use each tool's strengths and avoid its weak spots |
| `work_orders.md` | WO01-WO12: one research run each, with start-here sources, what to extract, what to skip, target |
| `ready/` | **the prompts to paste** (generated; do not edit by hand) |
| `example_candidates.jsonl` | 5 real/bad candidates that exercise every check |

## Loop

```bash
python tools/build_research_prompts.py            # regenerate ready/ from the live KB (vocabulary, known varieties, thin spots)
# paste ready/WO03_chatgpt.md into ChatGPT Deep Research (or ready/WO07_grok.md into Grok); save Part A as batches/WO03.jsonl
agrihub kg ingest-candidates batches/WO03.jsonl     # verifies against Europe PMC / the documents; writes kg/incoming/WO03.yaml + .report.md
```

Read `kg/incoming/WO03.report.md`: the reason table says what to fix in the next prompt (e.g. many "quote not found" -> tell the model to copy, not summarise);
"entities the KG does not have" says what to add to the vocabulary. Read the **spot-check sample** against the sources. If >= 95 % are right:

```bash
git mv kg/incoming/WO03.yaml kg/curated/wo03_notified_varieties.yaml
agrihub kg build && agrihub kg verify-quotes
```

then `kg load --release ...`, compare with live, `kg promote`. Candidates in `*.needs_review.jsonl` can be fixed by hand (widen the quote with ` ... `, add `alias_in_quote`) and re-run.
`*.unverifiable.jsonl` are real-looking sources whose text could not be read from here (paywalled / only an abstract); verify them by hand or drop them.

## Why the output looks the way it does

- JSONL, one claim per line: a truncated answer loses lines, not the whole file, and every line is validated independently.
- The quote may be fragments joined by ` ... ` because the disease is often named in a table caption and the variety in a row; the checker verifies each fragment, in order.
- The model never supplies a title we trust, a method stronger than the source supports, or an identifier we do not re-derive: those come from Europe PMC and from caps in the tool.
