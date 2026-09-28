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

# Streamlit Community Cloud's secrets manager populates st.secrets, not the process environment --
# bridge it into os.environ so the plain os.environ.get(...) calls below (and the Export tab's
# subprocess, which inherits this process's environment) see DATABASE_URL_DIRECT/API_BASE_URL the
# same way they would from a local .env. A no-op locally, where no secrets.toml exists.
try:
    for _key, _value in st.secrets.items():
        os.environ.setdefault(_key, str(_value))
except Exception:
    pass

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
REPO_ROOT = Path(__file__).resolve().parents[2]
CROPS = ["wheat", "soybean", "chickpea"]
PROVIDERS = ["gemini", "openrouter", "groq"]  # matches curator.llm.client's real provider set

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
if "actioned" not in st.session_state:
    # staged_id -> "approved" | "rejected", for candidates actioned inline from the Extract tab's
    # cached result -- lets a card show its outcome immediately without re-fetching /lit/pending.
    st.session_state["actioned"] = {}

st.title("AgriHub GKB — paper extraction & review")
st.caption(
    "Every accepted candidate below already passed Europe PMC verification, LLM extraction, "
    "quote grounding, and entity resolution (curator/lit + curator/llm + curator/extract). "
    "Nothing here writes to the live knowledge graph -- approved claims land in a staging area "
    "and only reach a release through the normal `kg build`/`load`/`promote` cycle."
)

reviewer = st.text_input("Your name (recorded on every approve/reject)", value=st.session_state["reviewer"])
st.session_state["reviewer"] = reviewer


def _normalise_identifier(value: str) -> str:
    """Convert common PMID/DOI input forms to the API's canonical identifier."""
    identifier = value.strip()
    lower_identifier = identifier.lower()
    if lower_identifier.startswith("https://doi.org/"):
        return f"doi:{identifier[len('https://doi.org/'):]}"
    if lower_identifier.startswith("http://doi.org/"):
        return f"doi:{identifier[len('http://doi.org/'):]}"
    if lower_identifier.startswith("doi.org/"):
        return f"doi:{identifier[len('doi.org/'):]}"
    if identifier.lower().startswith("doi:"):
        return f"doi:{identifier[4:]}"
    if identifier.isdigit():
        return f"pmid:{identifier}"
    return identifier


def _score_badge(score: float | None) -> str:
    if score is None:
        return "no score"
    color = "green" if score >= 95 else ("orange" if score >= 92 else "red")
    return f":{color}[**{score:.0f}/100 match**]"


def _render_claim_card(
    item: dict, *, note: str | None = None, note_kind: str = "info",
    footer_caption: str | None = None, actionable: bool = True,
) -> None:
    """One claim card, reused by the Extract tab (accepted/flagged, freshly staged) and the Review
    tab (any status, any past extraction). `note` is an extra callout above the quote -- a flag
    reason, an AI source opinion, or nothing. `actionable` gates the inline Approve/Reject buttons;
    the Extract tab's "not extractable" cards pass False since there's no valid claim to act on."""
    staged_id = item.get("staged_id") or item.get("id")
    with st.container(border=True):
        st.markdown(f"**{item['subject_id']}** → `{item['claim_type']}` → **{item['object_id']}**")
        if item.get("qualifiers"):
            st.caption(" · ".join(f"{k}={v}" for k, v in item["qualifiers"].items()))
        if note:
            getattr(st, note_kind)(note)
        st.markdown(f"> {item['quote']}")
        st.markdown(
            f"{_score_badge(item.get('grounding_score'))} · "
            f"evidence method `{item['method']}` (weight {item['method_weight']:.2f})"
            + (f" — staged id {staged_id}" if staged_id else "")
        )
        if footer_caption:
            st.caption(footer_caption)

        if not actionable or staged_id is None:
            return

        outcome = st.session_state["actioned"].get(staged_id)
        if outcome == "approved":
            st.success(f"✅ Approved by {reviewer or 'you'}")
            return
        if outcome == "rejected":
            st.warning("❌ Rejected")
            return

        col_approve, col_reject, col_reason = st.columns([1, 1, 3])
        with col_approve:
            if st.button("✅ Approve", key=f"approve-{staged_id}", disabled=not reviewer.strip()):
                try:
                    _api_post(f"/lit/pending/{staged_id}/approve", {"reviewer": reviewer})
                except (ApiError, requests.RequestException) as exc:
                    st.error(f"Approve failed: {exc}")
                else:
                    st.session_state["actioned"][staged_id] = "approved"
                    st.rerun()
        with col_reject:
            reject_clicked = st.button("❌ Reject", key=f"reject-{staged_id}", disabled=not reviewer.strip())
        with col_reason:
            reason = st.text_input(
                "Reason (required to reject)", key=f"reason-{staged_id}",
                label_visibility="collapsed", placeholder="Reason (required to reject)",
            )
        if reject_clicked:
            if not reason.strip():
                st.error("A rejection reason is required.")
            else:
                try:
                    _api_post(f"/lit/pending/{staged_id}/reject", {"reviewer": reviewer, "reason": reason})
                except (ApiError, requests.RequestException) as exc:
                    st.error(f"Reject failed: {exc}")
                else:
                    st.session_state["actioned"][staged_id] = "rejected"
                    st.rerun()
        if not reviewer.strip():
            st.caption("Enter your name above to approve or reject.")


tab_extract, tab_review, tab_export = st.tabs(["Extract", "Review queue", "Export"])

# ─────────────────────────────── Extract tab ───────────────────────────────
with tab_extract:
    st.subheader("Extract candidate claims from a paper")
    st.caption(
        "Identifier-based only (a PMID or DOI verified live against Europe PMC) -- this is the "
        "only path with an automatic, trustworthy metadata check. A paper not indexed there needs "
        "its metadata typed and marked unverified by hand, which is a separate feature."
    )

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        crop = st.selectbox("Crop", CROPS)
    with col2:
        provider = st.selectbox(
            "LLM provider", PROVIDERS, index=0,
            help="Which LLM backend does the extraction. Gemini is the default; OpenRouter and "
                 "Groq are real alternatives, not placeholders -- useful for comparing results "
                 "on the same paper.",
        )
    with col3:
        identifier = st.text_input("PMID or DOI", placeholder="e.g. 34897256 or doi:10.5423/PPJ.FT.11.2021.0164")

    if st.button("Extract", type="primary", disabled=not identifier.strip()):
        pmid_or_doi = _normalise_identifier(identifier)
        with st.spinner(f"Fetching, verifying, extracting ({provider}), grounding..."):
            try:
                st.session_state["last_extraction"] = _api_post(
                    "/lit/extract", {"identifier": pmid_or_doi, "crop": crop, "provider": provider}
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

        summary = result.get("paper_summary")
        if summary and summary.get("bullets"):
            st.markdown("**Key findings** (AI digest, not verified claims):")
            for bullet in summary["bullets"]:
                st.markdown(f"- {bullet}")

        accepted, flagged, rejected = result["accepted"], result["flagged"], result["rejected"]
        st.markdown(
            f"**{len(accepted)} ready to approve · {len(flagged)} need your review · "
            f"{len(rejected)} not extractable** — extracted with `{result['provider']}`"
        )

        st.markdown("#### ✅ Ready to approve")
        st.caption("Grounded automatically: the quote matched the source text and named both parties.")
        if not accepted:
            st.caption("None this time.")
        for item in accepted:
            _render_claim_card(item)

        st.markdown("#### 🟡 Needs your review")
        st.caption(
            "The claim resolved to real entities, but the quote didn't clear the automated match "
            "threshold -- often because the disease/gene name is only in a nearby sentence, not "
            "repeated in the exact quote. Read the quote yourself and decide."
        )
        if not flagged:
            st.caption("None this time.")
        for item in flagged:
            _render_claim_card(item, note=f"⚠️ Flagged: {item['flag_reason']}", note_kind="warning")

        st.markdown("#### ⚪ Not extractable")
        st.caption(
            "No valid claim could be built -- an unresolvable entity, an unsupported claim type, "
            "or a schema issue. Shown for transparency; nothing here can be approved as-is."
        )
        if not rejected:
            st.caption("None this time.")
        for item in rejected:
            with st.container(border=True):
                header = " → ".join(
                    part for part in [item.get("claim_type"), item.get("subject_text"), item.get("object_text")] if part
                )
                if header:
                    st.markdown(f"*{header}*")
                if item.get("quote"):
                    st.markdown(f"> {item['quote']}")
                score = item.get("grounding_score")
                score_note = f" (grounding score {score:.0f}/100)" if score is not None else ""
                st.caption(f"{item['reason']}{score_note}")

# ─────────────────────────────── Review tab ───────────────────────────────
with tab_review:
    st.subheader("Pending review")
    st.caption(
        "The durable backlog across every past extraction -- not just the one you just ran. "
        "Includes both grounded-automatically candidates and ones flagged for your judgment."
    )
    if st.button("Refresh"):
        st.rerun()

    pending: list[dict] = []
    try:
        pending = _api_get("/lit/pending", status="pending_review")
        pending += _api_get("/lit/pending", status="needs_review")
    except ApiError as exc:
        st.error(f"Could not list pending claims: {exc}")
    except requests.RequestException as exc:
        st.error(f"Could not reach the API at {API_BASE_URL}: {exc}")

    if not pending:
        st.caption("Nothing pending review right now.")

    for row in sorted(pending, key=lambda r: r["id"], reverse=True):
        flag_reason = row.get("flag_reason")
        note = f"⚠️ Flagged: {flag_reason}" if flag_reason else None
        source_note = (
            f"Source: *{row['source_title']}* ({row.get('source_year') or '?'}) "
            f"{'✅ verified' if row['source_verified'] else '⚠️ not verified'}"
        )
        relevance = row.get("source_relevance")
        if relevance and relevance.get("notes"):
            source_note += f" · AI opinion: {relevance['notes']}"
        _render_claim_card(row, note=note, note_kind="warning" if note else "info", footer_caption=source_note)

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
