# claim_retry_v1

A corrective second pass, distinct from claim_extraction_v1/v2.md's up-front extraction prompt.
Used only when `curator.lit.run_extraction.extract_paper(..., retry=True)` -- opt-in, off by
default. Built after two different up-front prompt interventions (claim_extraction_v1's added
rules, then the v2 few-shot rewrite) both failed to fix the same 3 recurring failure patterns found
in the 5-paper pilot (PHASES.md items 29-31); this tries showing the model its own specific mistake
after the fact instead of trying to prevent every mistake in advance. Version string
`claim_retry_v1` is appended to the resulting `Evidence.extractor` field as `+retry` when a
candidate is only accepted after this pass, so a retry-rescued claim is always visible as such in
the data, never indistinguishable from a first-try success.

---

You previously extracted a candidate knowledge-graph claim from the source text below, but it was
rejected by an automated check. You will be given the source text, the candidate you produced, and
the exact reason it was rejected. Produce ONE corrected JSON object with the same shape as the
candidate (`claim_type`, `subject`, `object`, `qualifiers`, `evidence`), fixing the specific problem
named in the rejection reason — or return the literal JSON value `null` if, on reflection, the
source text genuinely does not support this claim at all.

Return ONLY the corrected JSON object or `null`. No prose, no markdown fences, no array wrapper.

## Common fixes, by rejection reason

- **"quote does not mention: X"** — the entity named `X` isn't in your quote. If `X`'s name appears
  in a sentence immediately before or after the one you quoted, extend your quote to include that
  adjacent sentence too (quotes may span multiple contiguous sentences, verbatim, exactly as they
  appear back-to-back in the source text). Do not invent a mention of `X` that isn't really there.
- **"quote does not match the source text closely enough (possible paraphrase or fabrication)"** —
  your quote isn't an exact substring of the source text. Copy the sentence(s) character for
  character from the source text given below; do not paraphrase, summarize, or lightly reword them.
- **"could not resolve object ..." for a `GENE_CONFERS_RESISTANCE` claim** — this claim type's
  object must always be the **Disease**, never the Pathogen/organism, even when the sentence you
  quoted only names the pathogen (e.g. "resistant to all known races of X" where X is the pathogen).
  If the disease's name is in a nearby sentence, extend your quote to include it and set
  `object: {"type": "Disease", "text": "<the disease name>"}`.
- **"could not resolve subject/object ..."** for any other reason — the text you gave doesn't match
  any entity in the knowledge base's vocabulary under that exact wording. If a different, more
  standard form of the name appears in the source text (e.g. the full name instead of an
  abbreviation, or vice versa), use whichever form is what your quote actually contains. If you
  cannot find a wording likely to resolve, it's fine to return `null` — a corrected guess is not
  better than admitting the entity can't be identified from this text.
- **"claim_type ... is not extracted by this pipeline yet"** or **"unknown claim_type"** — this
  cannot be fixed by rewording; return `null`.
- **"quote shorter than 20 characters"** — your quote was too short to be a real sentence. Quote the
  full sentence(s) that state the fact, not just a fragment.

## What you are given

```
SOURCE TEXT:
<the full text extract_paper fetched for this paper -- abstract or full text>

CANDIDATE THAT WAS REJECTED:
<the exact JSON object you produced, unchanged>

REJECTION REASON:
<the exact automated rejection reason string>
```

Respond with the corrected JSON object, or `null`.
