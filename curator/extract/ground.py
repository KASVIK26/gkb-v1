"""Verify that an LLM-extracted quote is real (RESEARCH_ROADMAP.md Sec 6's grounding check).

Two independent checks, both must pass:
  1. The quote is genuinely present in the source text (fuzzy match, tolerating minor whitespace/
     OCR-style differences but not a paraphrase or a merge of unrelated sentences).
  2. The subject and object entity mentions the LLM claims the quote supports actually appear in
     that quote -- catches a quote that is real but doesn't actually mention both parties.

Nothing here ever "corrects" or rewrites a quote. A candidate either passes as-is or is rejected
with a stated reason.
"""

from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

from curator.model.claims import MIN_QUOTE_CHARS

DEFAULT_THRESHOLD = 92


@dataclass(frozen=True)
class GroundingResult:
    passed: bool
    reason: str | None = None
    score: float = 0.0  # rapidfuzz partial_ratio (0-100); a transparency signal for the reviewer,
                        # not itself the pass/fail criterion -- `passed` already reflects `threshold`.


def quote_match_score(quote: str, source_text: str) -> float:
    """The raw rapidfuzz partial_ratio (0-100) between `quote` and `source_text`, 0 for an empty quote."""
    if not quote or not quote.strip():
        return 0.0
    return fuzz.partial_ratio(quote, source_text)


def verify_quote(quote: str, source_text: str, *, threshold: int = DEFAULT_THRESHOLD) -> bool:
    """True if `quote` is a genuine (fuzzy-matched) substring of `source_text`."""
    return quote_match_score(quote, source_text) >= threshold


def entities_present(quote: str, mentions: list[str]) -> bool:
    """True if every mention (subject/object free text) appears in the quote, case-insensitively."""
    quote_lower = quote.lower()
    return all(mention.lower() in quote_lower for mention in mentions if mention)


def ground_candidate(
    *,
    quote: str,
    source_text: str,
    entity_mentions: list[str],
    threshold: int = DEFAULT_THRESHOLD,
) -> GroundingResult:
    """Run both grounding checks plus the model's own minimum-quote-length rule.

    `entity_mentions` should be the free-text subject/object mentions the LLM attached to this
    candidate; pass only the ones that name an actual entity (skip a free-text environmental/
    management description, which won't literally repeat inside its own supporting quote).
    """
    score = quote_match_score(quote, source_text)
    if len((quote or "").strip()) < MIN_QUOTE_CHARS:
        return GroundingResult(passed=False, reason=f"quote shorter than {MIN_QUOTE_CHARS} characters", score=score)
    if score < threshold:
        return GroundingResult(
            passed=False,
            reason="quote does not match the source text closely enough (possible paraphrase or fabrication)",
            score=score,
        )
    if entity_mentions and not entities_present(quote, entity_mentions):
        missing = [m for m in entity_mentions if m and m.lower() not in quote.lower()]
        return GroundingResult(
            passed=False,
            reason=f"quote does not mention: {', '.join(missing)}",
            score=score,
        )
    return GroundingResult(passed=True, score=score)
