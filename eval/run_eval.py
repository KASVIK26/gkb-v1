"""Phase 6 evaluation harness (RESEARCH_ROADMAP.md Sec 6.1/6.3).

Scores a real curator.lit.run_extraction.extract_paper() run against a hand-annotated gold file
(docs/annotation_guidelines.md, eval/schema.py), reporting strict/relaxed claim precision/recall/F1,
grounding scores, rejection reasons, and two categories of gold claim that are deliberately excluded
from precision/recall rather than silently miscounted: claims whose object needs a human-built
entity (a known Phase-5 design decision, not a model failure) and claims the annotator could not
resolve against the current KG vocab (a real coverage gap, not an annotation error).

Every run is live -- real Europe PMC fetch, real LLM call -- by design; this project does not
fabricate or cache a "result" to make a metric look good. See eval/run_eval.py's own CLI:

    python -m eval.run_eval run --gold eval/gold/wheat_pilot.jsonl --identifier pmid:19229000 --crop wheat
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import typer

from curator.lit.run_extraction import ExtractionResult, extract_paper
from curator.model.enums import ClaimType
from eval.schema import GoldClaim, load_gold

# DISEASE_ENV_TRIGGER/DISEASE_MANAGED_BY objects are always brand-new entities that
# build_claim_candidate deliberately routes to "needs a human" (curator/extract/normalize.py) --
# excluded from precision/recall so the pipeline isn't penalized for a decision already made on
# purpose in Phase 5. See docs/annotation_guidelines.md Sec 2.
NEEDS_HUMAN_ENTITY = frozenset({ClaimType.DISEASE_ENV_TRIGGER, ClaimType.DISEASE_MANAGED_BY})


def strict_key(claim_type: str, subject_id: str | None, object_id: str | None, qualifiers: dict[str, Any]) -> tuple:
    return (claim_type, subject_id, object_id, tuple(sorted(qualifiers.items())))


def relaxed_key(claim_type: str, subject_id: str | None, object_id: str | None) -> tuple:
    return (claim_type, subject_id, object_id)


@dataclass
class EvalReport:
    strict_tp: int
    strict_fp: int
    strict_fn: int
    relaxed_tp: int
    relaxed_fp: int
    relaxed_fn: int
    gold_unresolvable: list[GoldClaim] = field(default_factory=list)
    gold_needs_human_entity: list[GoldClaim] = field(default_factory=list)
    rejected_reasons: Counter = field(default_factory=Counter)
    grounding_scores: list[float] = field(default_factory=list)

    @property
    def extra_predicted(self) -> int:
        """Predicted claims whose relaxed key matches no gold claim at all -- candidates for
        manual hallucination review, not an automatic verdict (gold coverage may itself be
        incomplete, especially on a 2-paper pilot)."""
        return self.relaxed_fp

    @staticmethod
    def _prf(tp: int, fp: int, fn: int) -> tuple[float | None, float | None, float | None]:
        precision = tp / (tp + fp) if (tp + fp) > 0 else None
        recall = tp / (tp + fn) if (tp + fn) > 0 else None
        f1 = (2 * precision * recall / (precision + recall)) if precision and recall and (precision + recall) > 0 else None
        return precision, recall, f1

    @property
    def precision_strict(self) -> float | None:
        return self._prf(self.strict_tp, self.strict_fp, self.strict_fn)[0]

    @property
    def recall_strict(self) -> float | None:
        return self._prf(self.strict_tp, self.strict_fp, self.strict_fn)[1]

    @property
    def f1_strict(self) -> float | None:
        return self._prf(self.strict_tp, self.strict_fp, self.strict_fn)[2]

    @property
    def precision_relaxed(self) -> float | None:
        return self._prf(self.relaxed_tp, self.relaxed_fp, self.relaxed_fn)[0]

    @property
    def recall_relaxed(self) -> float | None:
        return self._prf(self.relaxed_tp, self.relaxed_fp, self.relaxed_fn)[1]

    @property
    def f1_relaxed(self) -> float | None:
        return self._prf(self.relaxed_tp, self.relaxed_fp, self.relaxed_fn)[2]

    def render(self) -> str:
        def fmt(x: float | None) -> str:
            return "n/a" if x is None else f"{x:.2f}"

        lines = [
            "| Metric | Strict | Relaxed |",
            "|---|---|---|",
            f"| Precision | {fmt(self.precision_strict)} | {fmt(self.precision_relaxed)} |",
            f"| Recall | {fmt(self.recall_strict)} | {fmt(self.recall_relaxed)} |",
            f"| F1 | {fmt(self.f1_strict)} | {fmt(self.f1_relaxed)} |",
            f"| TP/FP/FN | {self.strict_tp}/{self.strict_fp}/{self.strict_fn} | {self.relaxed_tp}/{self.relaxed_fp}/{self.relaxed_fn} |",
            "",
            f"Extra predicted claims with no matching gold fact at all (possible hallucinations -- "
            f"needs manual review, gold coverage may be incomplete): {self.extra_predicted}",
            f"Gold claims needing a human-built entity before they can become a Claim (known Phase 5 "
            f"limitation, excluded from the table above): {len(self.gold_needs_human_entity)}",
            f"Gold claims unresolvable against the current KG vocab (real coverage gaps, excluded "
            f"from the table above): {len(self.gold_unresolvable)}",
        ]
        if self.grounding_scores:
            mean_score = sum(self.grounding_scores) / len(self.grounding_scores)
            lines.append(
                f"Grounding scores of accepted candidates: min={min(self.grounding_scores):.1f} "
                f"mean={mean_score:.1f} max={max(self.grounding_scores):.1f}"
            )
        if self.rejected_reasons:
            lines.append("Rejection reasons:")
            for reason, count in self.rejected_reasons.most_common():
                lines.append(f"- ({count}x) {reason}")
        return "\n".join(lines)


def score_extraction(gold: list[GoldClaim], result: ExtractionResult) -> EvalReport:
    needs_human = [g for g in gold if g.claim_type in NEEDS_HUMAN_ENTITY]
    remaining = [g for g in gold if g.claim_type not in NEEDS_HUMAN_ENTITY]
    unresolvable = [g for g in remaining if g.subject_id is None or g.object_id is None]
    evaluable = [g for g in remaining if g.subject_id is not None and g.object_id is not None]

    gold_strict = {strict_key(g.claim_type.value, g.subject_id, g.object_id, g.qualifiers) for g in evaluable}
    gold_relaxed = {relaxed_key(g.claim_type.value, g.subject_id, g.object_id) for g in evaluable}

    predicted_strict = {
        strict_key(c.claim.type.value, c.claim.subject_id, c.claim.object_id, c.claim.qualifiers)
        for c in result.accepted
    }
    predicted_relaxed = {
        relaxed_key(c.claim.type.value, c.claim.subject_id, c.claim.object_id) for c in result.accepted
    }

    return EvalReport(
        strict_tp=len(gold_strict & predicted_strict),
        strict_fp=len(predicted_strict - gold_strict),
        strict_fn=len(gold_strict - predicted_strict),
        relaxed_tp=len(gold_relaxed & predicted_relaxed),
        relaxed_fp=len(predicted_relaxed - gold_relaxed),
        relaxed_fn=len(gold_relaxed - predicted_relaxed),
        gold_unresolvable=unresolvable,
        gold_needs_human_entity=needs_human,
        rejected_reasons=Counter(r.reason for r in result.rejected),
        grounding_scores=[c.grounding_score for c in result.accepted],
    )


app = typer.Typer(help="Phase 6 evaluation harness -- scores a live extraction against a gold file.")


@app.command()
def run(
    gold: Path = typer.Option(..., help="Path to a gold JSONL file, e.g. eval/gold/wheat_pilot.jsonl"),
    identifier: str = typer.Option(..., help="pmid:<digits> or doi:<doi> -- the paper the gold file annotates"),
    crop: str = typer.Option(..., help="wheat | soybean | chickpea"),
    model: str = typer.Option(None, help="Override the default LLM model (for later ablations)"),
    prompt_version: str = typer.Option(
        None, "--prompt-version", help="e.g. claim_extraction_v2 -- default: the production v1 prompt"
    ),
    retry: bool = typer.Option(
        False, "--retry", help="Give a rejected candidate one corrective pass (claim_retry_v1.md) before giving up"
    ),
    backend: str = typer.Option(
        "custom", "--backend",
        help="'custom' (curator.lit.run_extraction, default) or 'langextract' (curator.extract.langextract_pipeline)",
    ),
    extraction_passes: int = typer.Option(
        3, "--extraction-passes", help="langextract backend only: number of pooled extraction passes"
    ),
    provider: str = typer.Option(
        "openrouter", "--provider", help="custom backend only: openrouter | gemini | groq"
    ),
) -> None:
    """Run a real extraction (live Europe PMC + live LLM) and score it against a gold file.

    `gold` may contain claims annotated from several different papers (e.g. one file per crop or
    per batch) -- only the records whose `source_id` matches `identifier` are scored against this
    run, so a multi-paper gold file never penalizes recall for a fact that belongs to a different
    paper entirely.
    """
    all_gold = load_gold(gold)
    gold_claims = [g for g in all_gold if g.source_id == identifier]
    if not gold_claims:
        typer.echo(
            f"Warning: no gold claims in {gold} have source_id == {identifier!r} "
            f"({len(all_gold)} total in file, for other papers)."
        )
    if backend == "langextract":
        from curator.extract.langextract_pipeline import GEMINI_DEFAULT_MODEL, extract_paper_langextract
        result = extract_paper_langextract(
            identifier, crop=crop, model=model or GEMINI_DEFAULT_MODEL, extraction_passes=extraction_passes
        )
    elif backend == "custom":
        from curator.llm.client import LLMClient
        llm_client = LLMClient(provider=provider) if provider != "openrouter" else None
        result = extract_paper(
            identifier, crop=crop, llm_client=llm_client, model=model,
            prompt_version=prompt_version, retry=retry,
        )
    else:
        raise typer.BadParameter(f"Unknown backend {backend!r}; expected 'custom' or 'langextract'")
    report = score_extraction(gold_claims, result)
    typer.echo(f"Source: {result.source.title} ({result.source.id})")
    typer.echo(f"Accepted: {len(result.accepted)}  Rejected: {len(result.rejected)}  Gold: {len(gold_claims)}")
    typer.echo("")
    typer.echo(report.render())


if __name__ == "__main__":
    app()
