"""Paper search/extraction/review endpoints -- the HTTP surface over curator.lit/llm/extract.

This router is a thin wrapper: all extraction, grounding, and entity-resolution logic already
lives in curator/lit/run_extraction.py (unchanged). This file's only new responsibility is writing
accepted candidates into staging.pending_claim/staging.pending_source (curator/graph/staging.py)
and exposing the review actions (list/approve/reject) over HTTP for tools/review_app/.
"""

from __future__ import annotations

from typing import Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from curator.graph import staging
from curator.lit import europepmc
from curator.lit.run_extraction import extract_paper
from curator.llm.client import LLMClient, LLMClientError
from curator.llm.source_assessment import assess_source
from curator.model.enums import EVIDENCE_WEIGHT, EvidenceMethod

from api.deps import get_db, get_llm_client

router = APIRouter(prefix="/lit", tags=["lit"])


def _model_from_extractor(extractor: str) -> str:
    """"llm:<model>@<prompt_version>" -> "<model>"."""
    body = extractor.removeprefix("llm:")
    return body.split("@", 1)[0]


class ExtractRequest(BaseModel):
    identifier: str = Field(..., description="pmid:<digits> or doi:<doi>, e.g. pmid:34897256")
    crop: str = Field(..., description="wheat | soybean | chickpea")


class AcceptedOut(BaseModel):
    staged_id: int
    claim_type: str
    subject_id: str
    object_id: str
    qualifiers: dict[str, Any]
    quote: str
    locator: str | None
    method: str
    method_weight: float
    grounding_score: float
    extractor: str


class RejectedOut(BaseModel):
    reason: str


class SourceAssessmentOut(BaseModel):
    relevant: bool | None
    notes: str


class ExtractResponse(BaseModel):
    source_id: str
    source_title: str
    source_venue: str | None
    source_year: int | None
    source_verified: bool
    source_assessment: SourceAssessmentOut | None
    accepted: list[AcceptedOut]
    rejected: list[RejectedOut]


@router.post("/extract", response_model=ExtractResponse)
def extract(
    req: ExtractRequest,
    conn: psycopg.Connection = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
) -> ExtractResponse:
    try:
        result = extract_paper(req.identifier, crop=req.crop, llm_client=llm)
    except europepmc.PublicationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except europepmc.EuropePMCError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {exc}") from exc

    # Source assessment is advisory only -- a failure here must never break extraction itself.
    assessment_out: SourceAssessmentOut | None = None
    assessment_dict: dict[str, Any] | None = None
    try:
        abstract = europepmc.fetch_abstract(req.identifier) or ""
        assessment = assess_source(
            title=result.source.title,
            venue=result.source.venue,
            year=result.source.year,
            abstract=abstract[:4000],
            crop=req.crop,
            llm_client=llm,
        )
        assessment_out = SourceAssessmentOut(relevant=assessment.relevant, notes=assessment.notes)
        assessment_dict = {"relevant": assessment.relevant, "notes": assessment.notes}
    except Exception:  # noqa: BLE001 -- advisory signal only, never propagate
        assessment_out = None

    staging.ensure_staging_schema(conn)
    staging.insert_pending_source(conn, result.source)

    accepted_out: list[AcceptedOut] = []
    for item in result.accepted:
        staged_id = staging.insert_pending_claim(
            conn,
            claim=item.claim,
            evidence=item.evidence,
            llm_model=_model_from_extractor(item.evidence.extractor),
            grounding_score=item.grounding_score,
            source_relevance=assessment_dict,
        )
        accepted_out.append(
            AcceptedOut(
                staged_id=staged_id,
                claim_type=item.claim.type.value,
                subject_id=item.claim.subject_id,
                object_id=item.claim.object_id,
                qualifiers=item.claim.qualifiers,
                quote=item.evidence.quote or "",
                locator=item.evidence.locator,
                method=item.evidence.method.value,
                method_weight=EVIDENCE_WEIGHT[item.evidence.method],
                grounding_score=item.grounding_score,
                extractor=item.evidence.extractor,
            )
        )

    return ExtractResponse(
        source_id=result.source.id,
        source_title=result.source.title,
        source_venue=result.source.venue,
        source_year=result.source.year,
        source_verified=result.source.verified,
        source_assessment=assessment_out,
        accepted=accepted_out,
        rejected=[RejectedOut(reason=r.reason) for r in result.rejected],
    )


class PendingOut(BaseModel):
    id: int
    claim_type: str
    subject_id: str
    object_id: str
    qualifiers: dict[str, Any]
    status: str
    source_id: str
    source_title: str
    source_venue: str | None
    source_year: int | None
    source_verified: bool
    method: str
    method_weight: float
    extractor: str
    locator: str | None
    quote: str | None
    llm_model: str | None
    grounding_score: float | None
    source_relevance: dict[str, Any] | None


@router.get("/pending", response_model=list[PendingOut])
def list_pending(status: str = "pending_review", conn: psycopg.Connection = Depends(get_db)) -> list[PendingOut]:
    rows = staging.list_pending(conn, status=status)
    return [
        PendingOut(
            id=row["id"],
            claim_type=row["claim_type"],
            subject_id=row["subject_id"],
            object_id=row["object_id"],
            qualifiers=row["qualifiers"],
            status=row["status"],
            source_id=row["source_id"],
            source_title=row["source_title"],
            source_venue=row["source_venue"],
            source_year=row["source_year"],
            source_verified=row["source_verified"],
            method=row["method"],
            method_weight=EVIDENCE_WEIGHT[EvidenceMethod(row["method"])],
            extractor=row["extractor"],
            locator=row["locator"],
            quote=row["quote"],
            llm_model=row["llm_model"],
            grounding_score=row["grounding_score"],
            source_relevance=row["source_relevance"],
        )
        for row in rows
    ]


class ReviewAction(BaseModel):
    reviewer: str = Field(..., min_length=1)


class RejectAction(ReviewAction):
    reason: str = Field(..., min_length=1)


@router.post("/pending/{claim_id}/approve")
def approve(claim_id: int, body: ReviewAction, conn: psycopg.Connection = Depends(get_db)) -> dict[str, str]:
    staging.approve_pending(conn, claim_id, reviewer=body.reviewer)
    return {"status": "approved"}


@router.post("/pending/{claim_id}/reject")
def reject(claim_id: int, body: RejectAction, conn: psycopg.Connection = Depends(get_db)) -> dict[str, str]:
    staging.reject_pending(conn, claim_id, reviewer=body.reviewer, reason=body.reason)
    return {"status": "rejected"}
