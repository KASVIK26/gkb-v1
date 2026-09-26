"""A short, separate LLM call giving a reviewer an AI *opinion* on whether a paper is worth
extracting from -- distinct from grounding (checks a quote against text) and from Europe PMC
verification (confirms the paper is real). See curator/llm/prompts/source_assessment_v1.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from curator.llm.client import DEFAULT_MODEL, LLMClient

_PROMPT_VERSION = "source_assessment_v1"


@dataclass(frozen=True)
class SourceAssessment:
    relevant: bool | None  # None when the LLM response couldn't be parsed -- never guessed as True
    notes: str


def _load_prompt() -> str:
    return Path(__file__).resolve().parent.joinpath(
        "prompts", f"{_PROMPT_VERSION}.md"
    ).read_text(encoding="utf-8")


def assess_source(
    *,
    title: str,
    venue: str | None,
    year: int | None,
    abstract: str,
    crop: str,
    llm_client: LLMClient | None = None,
    model: str | None = None,
) -> SourceAssessment:
    """Ask the LLM for a one-line opinion on this paper's relevance/credibility for `crop`.

    Never raises on a malformed LLM response -- returns relevant=None with a note explaining that,
    since this signal is advisory only and must never block or silently skip extraction.
    """
    client = llm_client or LLMClient()
    user = (
        f"Title: {title}\nVenue: {venue or 'unknown'}\nYear: {year or 'unknown'}\n"
        f"Target crop: {crop}\n\nAbstract:\n{abstract}"
    )
    response = client.complete(_load_prompt(), user, model=model or DEFAULT_MODEL)

    try:
        parsed = json.loads(response.content)
        return SourceAssessment(relevant=bool(parsed["relevant"]), notes=str(parsed.get("notes", "")))
    except (json.JSONDecodeError, KeyError, TypeError):
        return SourceAssessment(relevant=None, notes="Could not parse the model's source assessment.")
