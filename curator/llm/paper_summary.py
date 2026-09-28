"""A short, separate LLM call giving a researcher a bullet-point digest of a paper's own findings --
distinct from claim extraction (structured, grounded candidates) and source_assessment (an opinion
on relevance/credibility). See curator/llm/prompts/paper_summary_v1.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from curator.llm.client import LLMClient

_PROMPT_VERSION = "paper_summary_v1"


@dataclass(frozen=True)
class PaperSummary:
    bullets: list[str]  # empty when the LLM response couldn't be parsed -- never fabricated


def _load_prompt() -> str:
    return Path(__file__).resolve().parent.joinpath(
        "prompts", f"{_PROMPT_VERSION}.md"
    ).read_text(encoding="utf-8")


def summarize_paper(
    *,
    title: str,
    venue: str | None,
    year: int | None,
    text: str,
    crop: str,
    llm_client: LLMClient | None = None,
    model: str | None = None,
) -> PaperSummary:
    """Ask the LLM for a bullet-point digest of this paper's own findings, for `crop`.

    Never raises on a malformed LLM response -- returns an empty bullet list, since this signal is
    advisory only and must never block or silently skip extraction.
    """
    client = llm_client or LLMClient()
    user = (
        f"Title: {title}\nVenue: {venue or 'unknown'}\nYear: {year or 'unknown'}\n"
        f"Target crop: {crop}\n\nText:\n{text}"
    )
    # `model=model`, not `model or DEFAULT_MODEL` -- see curator/lit/run_extraction.py and
    # curator/llm/source_assessment.py for the bug this avoids: forcing a hardcoded default here
    # would override whatever provider the caller's llm_client actually is.
    response = client.complete(_load_prompt(), user, model=model)

    try:
        parsed = json.loads(response.content)
        return PaperSummary(bullets=[str(b) for b in parsed.get("bullets", [])])
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
        return PaperSummary(bullets=[])
