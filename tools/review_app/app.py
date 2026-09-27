"""Streamlit review app for the paper-extraction pipeline (RESEARCH_ROADMAP.md task 5.10,
TECH_STACK.md M9). A local tool for now -- no auth beyond whatever protects your machine; when this
is ever deployed, put it behind Cloudflare Access (see README.md in this directory).

Talks to the api/ FastAPI service over HTTP only -- no direct DB or LLM access from here, so all
trust logic (grounding, normalization, what gets staged) lives in exactly one place.

Run: streamlit run tools/review_app/app.py
Needs: the api/ service running (uvicorn api.main:app --reload), API_BASE_URL env var if not on
the default http://localhost:8000, and a repo checkout for the Export tab's `agrihub` CLI call.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import requests
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
REPO_ROOT = Path(__file__).resolve().parents[2]
CROPS = ["wheat", "soybean", "chickpea"]

st.set_page_config(page_title="GKB paper review", layout="wide")


class ApiError(RuntimeError):
    """The API responded with a non-2xx status -- carries the server's own error detail message."""


def _raise_for_status(response: requests.Response) -> None:
    if response.ok:
        return
    if response.headers.get("content-type", "").startswith("application/json"):
        detail = response.json().get("detail", response.text)
    else:
        detail = response.text
    raise ApiError(detail)


def _api_get(path: str, **params):
    response = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=120)
    _raise_for_status(response)
    return response.json()


def _api_post(path: str, json: dict):
    response = requests.post(f"{API_BASE_URL}{path}", json=json, timeout=120)
    _raise_for_status(response)
    return response.json()


if "reviewer" not in st.session_state:
    st.session_state["reviewer"] = ""
if "last_extraction" not in st.session_state:
    st.session_state["last_extraction"] = None

st.title("AgriHub GKB — paper extraction & review")
st.caption(
    "Every accepted candidate below already passed Europe PMC verification, LLM extraction, "
    "quote grounding, and entity resolution (curator/lit + curator/llm + curator/extract). "
    "Nothing here writes to the live knowledge graph -- approved claims land in a staging area "
    "and only reach a release through the normal `kg build`/`load`/`promote` cycle."
)

reviewer = st.text_input("Your name (recorded on every approve/reject)", value=st.session_state["reviewer"])
st.session_state["reviewer"] = reviewer

tab_extract, tab_review, tab_export = st.tabs(["Extract", "Review queue", "Export"])

# ─────────────────────────────── Extract tab ───────────────────────────────
with tab_extract:
    st.subheader("Extract candidate claims from a paper")
    st.caption(
        "Identifier-based only (a PMID or DOI verified live against Europe PMC) -- this is the "
        "only path with an automatic, trustworthy metadata check. A paper not indexed there needs "
        "its metadata typed and marked unverified by hand, which is a separate feature."
    )

    col1, col2 = st.columns([1, 2])
    with col1:
        crop = st.selectbox("Crop", CROPS)
    with col2:
        identifier = st.text_input("PMID or DOI", placeholder="e.g. 34897256 or doi:10.5423/PPJ.FT.11.2021.0164")

    if st.button("Extract", type="primary", disabled=not identifier.strip()):
        pmid_or_doi = identifier.strip() if ":" in identifier else f"pmid:{identifier.strip()}"
        with st.spinner("Fetching, verifying, extracting, grounding..."):
            try:
                st.session_state["last_extraction"] = _api_post(
                    "/lit/extract", {"identifier": pmid_or_doi, "crop": crop}
                )
            except ApiError as exc:
                st.session_state["last_extraction"] = None
                st.error(f"Extraction failed: {exc}")
            except requests.RequestException as exc:
                st.session_state["last_extraction"] = None
                st.error(f"Could not reach the API at {API_BASE_URL}: {exc}")

    result = st.session_state["last_extraction"]
    if result:
        verified_badge = "✅ verified via Europe PMC" if result["source_verified"] else "⚠️ NOT verified"
        st.markdown(f"### {result['source_title']}")
        st.caption(f"{result.get('source_venue') or 'unknown venue'}, {result.get('source_year') or 'unknown year'} — {verified_badge}")

        assessment = result.get("source_assessment")
        if assessment:
            icon = "🟢" if assessment["relevant"] else ("🟡" if assessment["relevant"] is False else "⚪")
            st.info(f"{icon} **AI opinion on this source** (not a fact): {assessment['notes']}")

        st.markdown(f"**{len(result['accepted'])} accepted, {len(result['rejected'])} rejected**")

        for item in result["accepted"]:
            with st.container(border=True):
                st.markdown(f"**{item['subject_id']}** → `{item['claim_type']}` → **{item['object_id']}**")
                if item["qualifiers"]:
                    st.caption(" · ".join(f"{k}={v}" for k, v in item["qualifiers"].items()))
                st.markdown(f"> {item['quote']}")
                score = item["grounding_score"]
                score_color = "green" if score >= 95 else ("orange" if score >= 92 else "red")
                st.markdown(
                    f":{score_color}[**{score:.0f}/100 match**] · "
                    f"evidence method `{item['method']}` (weight {item['method_weight']:.2f}) — "
                    f"staged as pending review (id {item['staged_id']})"
                )

        for rejected in result["rejected"]:
            st.warning(f"Rejected: {rejected['reason']}")

# ─────────────────────────────── Review tab ───────────────────────────────
with tab_review:
    st.subheader("Pending review")
    if st.button("Refresh"):
        st.rerun()

    try:
        pending = _api_get("/lit/pending", status="pending_review")
    except ApiError as exc:
        pending = []
        st.error(f"Could not list pending claims: {exc}")
    except requests.RequestException as exc:
        pending = []
        st.error(f"Could not reach the API at {API_BASE_URL}: {exc}")

    if not pending:
        st.caption("Nothing pending review right now.")

    for row in pending:
        with st.container(border=True):
            st.markdown(f"**{row['subject_id']}** → `{row['claim_type']}` → **{row['object_id']}**")
            if row["qualifiers"]:
                st.caption(" · ".join(f"{k}={v}" for k, v in row["qualifiers"].items()))
            st.markdown(f"> {row['quote']}")
            score = row.get("grounding_score")
            score_text = f"{score:.0f}/100 match" if score is not None else "no score"
            st.caption(
                f"{score_text} · method `{row['method']}` (weight {row['method_weight']:.2f}) · "
                f"source: *{row['source_title']}* ({row.get('source_year') or '?'}) "
                f"{'✅ verified' if row['source_verified'] else '⚠️ not verified'}"
            )
            relevance = row.get("source_relevance")
            if relevance:
                st.caption(f"AI source opinion: {relevance.get('notes', '')}")

            col_approve, col_reject, col_reason = st.columns([1, 1, 3])
            with col_approve:
                if st.button("✅ Approve", key=f"approve-{row['id']}", disabled=not reviewer.strip()):
                    try:
                        _api_post(f"/lit/pending/{row['id']}/approve", {"reviewer": reviewer})
                    except (ApiError, requests.RequestException) as exc:
                        st.error(f"Approve failed: {exc}")
                    else:
                        st.rerun()
            with col_reject:
                reject_clicked = st.button("❌ Reject", key=f"reject-{row['id']}", disabled=not reviewer.strip())
            with col_reason:
                reason = st.text_input("Reason (required to reject)", key=f"reason-{row['id']}", label_visibility="collapsed", placeholder="Reason (required to reject)")
            if reject_clicked:
                if not reason.strip():
                    st.error("A rejection reason is required.")
                else:
                    try:
                        _api_post(f"/lit/pending/{row['id']}/reject", {"reviewer": reviewer, "reason": reason})
                    except (ApiError, requests.RequestException) as exc:
                        st.error(f"Reject failed: {exc}")
                    else:
                        st.rerun()
            if not reviewer.strip():
                st.caption("Enter your name above to approve or reject.")

# ─────────────────────────────── Export tab ───────────────────────────────
with tab_export:
    st.subheader("Export approved claims to kg/curated/")
    st.caption(
        "This only writes a YAML file -- it does not touch the live knowledge graph. Review the "
        "file, `git add` it, then run `agrihub kg build` (and `kg load`/`kg promote` when ready) "
        "yourself."
    )
    default_name = f"kg/curated/pending_{date.today():%Y_%m_%d}.yaml"
    out_path = st.text_input("Output path", value=default_name)

    if st.button("Export approved claims", type="primary"):
        full_path = REPO_ROOT / out_path
        result = subprocess.run(
            [sys.executable, "-m", "curator.cli", "lit", "export-staged", "--out", str(full_path)],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if result.returncode == 0:
            st.success(result.stdout)
            if full_path.exists():
                st.code(full_path.read_text(encoding="utf-8"), language="yaml")
        else:
            st.error(result.stdout + "\n" + result.stderr)
