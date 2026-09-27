"""Gold-annotation record schema (RESEARCH_ROADMAP.md Sec 6.1/6.2, docs/annotation_guidelines.md).

A GoldClaim is a human's (or a second, independent AI pass's) answer to "what claim does this paper
actually support here" -- written down in the same claim_type/qualifier vocabulary the pipeline
itself uses (curator.model.enums.ClaimType, curator.model.claims.QUALIFIERS), so eval/run_eval.py
can compare it directly against a real ExtractionResult without a translation layer that could hide
a mismatch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from curator.model.enums import ClaimType


class GoldClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str  # "pmid:<digits>" | "doi:<doi>" -- which paper this claim was annotated from,
    #                  so a harness run scoped to one paper can filter a multi-paper gold file
    #                  down to the claims that actually apply to it (see eval/run_eval.py's `run`).
    claim_type: ClaimType
    subject_text: str
    subject_id: str | None = None  # None = not resolvable against the current KG vocab -- a real
    #                                 coverage gap to report, not an annotation error.
    object_text: str
    object_id: str | None = None
    qualifiers: dict[str, Any] = {}
    quote: str
    section: str  # "abstract" | "full text" -- whichever text the annotator actually read
    ambiguous: bool = False
    annotator: str
    notes: str | None = None


def load_gold(path: Path | str) -> list[GoldClaim]:
    """Read one GoldClaim per non-blank line of a JSONL file."""
    records: list[GoldClaim] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(GoldClaim.model_validate(json.loads(line)))
    return records
