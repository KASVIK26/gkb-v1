"""Audit curated evidence: is every stored quote really in the source it cites?

The project's rule is that a fact is only as good as its verbatim quote, and the failure it guards against
is a plausible-looking citation that does not say what is claimed (RESEARCH_ROADMAP.md §2.2 D1/D2). This
re-fetches each cited paper from Europe PMC -- abstract, and the open-access full text including table rows
when there is one -- and checks every stored quote against it.

Statuses per evidence row:
  exact        the quote is a substring of the source text (after whitespace/quote/dash normalisation)
  fuzzy        very close but not identical (>= 95 partial match) -- worth a look, not trusted blindly
  missing      the source text was fetched and the quote is not in it
  no_text      the source could not be fetched, or only a paywalled abstract exists and the quote may
               come from the full text -- unverifiable here, NOT evidence of a problem
  not_on_page  a document fetched by URL does not contain the quote -- the URL may be a landing page, so
               this is unverified rather than wrong
  no_quote     the evidence row stores no quote (allowed for manual/official-document evidence)
  not_checked  the source is not a publication with a PMID/DOI (official documents, vocabularies)
"""

from __future__ import annotations

import html
import io
import json
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from rapidfuzz import fuzz

from curator.graph.bundle import KGBundle
from curator.lit import europepmc, jats
from curator.model import SourceType
from curator.lit.find_evidence import _DOCTYPE_RE, _squash, _table_rows

FUZZY_THRESHOLD = 95
_URL_CHECKED_TYPES = frozenset({SourceType.OFFICIAL_DOCUMENT, SourceType.TRIAL_REPORT, SourceType.CATALOGUE})


def normalise(text: str) -> str:
    text = html.unescape(text)  # Europe PMC titles arrive as "&lt;i&gt;Fusarium&lt;/i&gt;"
    text = re.sub(r"</?(?:i|b|em|strong|sub|sup|span|u)\b[^>]*>", "", text)  # inline formatting: no gap
    text = re.sub(r"<[^>]+>", " ", text)  # block tags (p, h4, br...) separate words
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"[‐-―−]", "-", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def fetch_source_text(source_id: str) -> str | None:
    """Abstract plus (when open access) the full text and table rows for a pmid:/doi: source, or None."""
    try:
        record = europepmc.get_record(source_id)
    except (europepmc.EuropePMCError, europepmc.PublicationNotFound):
        return None
    parts = [record.get("title") or "", europepmc.abstract_from_record(record) or ""]
    pmcid = record.get("pmcid")
    if record.get("isOpenAccess") == "Y" and pmcid:
        try:
            xml_text = europepmc.fetch_fulltext_xml(pmcid)
        except europepmc.EuropePMCError:
            xml_text = None
        if xml_text:
            try:
                parts.append(jats.extract_plain_text(xml_text))
                parts.extend(row for _, row in _table_rows(ET.fromstring(_DOCTYPE_RE.sub("", xml_text))))
            except ET.ParseError:
                pass
    return " ".join(p for p in parts if p)


_ELISION = re.compile(r"\.{3}|…|\[[^\]]*\]")  # "..." / "…" for cut text, [x] for an editorial insertion
MIN_FRAGMENT_CHARS = 12


def quote_fragments(quote: str) -> list[str]:
    """The verbatim stretches of a quote that a curator elided or edited with '...' or '[...]'."""
    pieces = [normalise(p) for p in _ELISION.split(quote)]
    return [p for p in pieces if len(p) >= MIN_FRAGMENT_CHARS] or [normalise(quote)]


MAX_DOCUMENT_BYTES = 25_000_000
_USER_AGENT = {"User-Agent": "Mozilla/5.0 (agrihub-kb quote audit)"}


def _read_url(url: str) -> bytes | None:
    request = urllib.request.Request(url, headers=_USER_AGENT)
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return response.read(MAX_DOCUMENT_BYTES)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def _read_archived(url: str) -> bytes | None:
    """The Internet Archive's closest snapshot of `url`, as the original bytes -- several Indian government
    servers are unreliable from outside India, and the curators already used archived copies of them."""
    lookup = _read_url("https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe=""))
    if not lookup:
        return None
    try:
        snapshot = json.loads(lookup)["archived_snapshots"]["closest"]["url"]
    except (KeyError, TypeError, ValueError):
        return None
    return _read_url(re.sub(r"/web/(\d+)/", r"/web/\1id_/", snapshot, count=1))  # id_ = the raw, unrewritten bytes


def _pdf_text(data: bytes) -> str | None:
    try:
        from pypdf import PdfReader  # optional: install the `audit` extra
    except ImportError:
        return None
    try:
        reader = PdfReader(io.BytesIO(data))
        return " ".join((page.extract_text() or "") for page in reader.pages[:400])
    except Exception:  # noqa: BLE001 -- a malformed PDF is "no text", never a crash
        return None


def fetch_url_text(url: str) -> str | None:
    """Visible text of an HTML page or PDF (official documents, institute pages), or None if unreachable."""
    data = _read_url(url) or _read_archived(url)
    if data is None:
        return None
    if data[:5] == b"%PDF-":
        return _pdf_text(data)
    raw = data.decode("utf-8", errors="replace")
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw))


def check_quote(quote: str, source_text: str) -> str:
    """exact: every fragment appears verbatim, in order. fuzzy: each is very close. missing: neither."""
    text = normalise(source_text)
    fragments = quote_fragments(quote)
    position, in_order = 0, True
    for fragment in fragments:
        found = text.find(fragment, position)
        if found < 0:
            in_order = False
            break
        position = found + len(fragment)
    if in_order:
        return "exact"
    return "fuzzy" if all(fuzz.partial_ratio(f, text) >= FUZZY_THRESHOLD for f in fragments) else "missing"


@dataclass(frozen=True)
class AuditRow:
    evidence_id: str
    claim_id: str
    source_id: str
    status: str
    quote: str | None
    locator: str | None


def audit_bundle(
    bundle: KGBundle,
    *,
    fetch: Callable[[str], str | None] = fetch_source_text,
    fetch_url: Callable[[str], str | None] = fetch_url_text,
) -> list[AuditRow]:
    source_by_id = {s.id: s for s in bundle.sources}
    texts: dict[str, str | None] = {}
    rows: list[AuditRow] = []
    for ev in bundle.evidence:
        source = source_by_id.get(ev.source_id)
        base = dict(evidence_id=ev.id, claim_id=ev.claim_id, source_id=ev.source_id, quote=ev.quote, locator=ev.locator)
        is_publication = ev.source_id.startswith(("pmid:", "doi:"))
        # Only documents quoted as text are fetched by URL; datasets/vocabularies hold computed values.
        fetchable = source is not None and source.type in _URL_CHECKED_TYPES
        url = source.url if fetchable and (source.url or "").startswith("http") else None
        if not (ev.quote or "").strip():
            rows.append(AuditRow(status="no_quote", **base))
            continue
        if not is_publication and url is None:
            rows.append(AuditRow(status="not_checked", **base))
            continue
        if ev.source_id not in texts:
            texts[ev.source_id] = fetch(ev.source_id) if is_publication else fetch_url(url)
        text = texts[ev.source_id]
        status = "no_text" if text is None else check_quote(ev.quote, text)
        # A "missing" quote from a paywalled paper may simply live in the full text we cannot read.
        if status == "missing" and not is_publication:
            status = "not_on_page"  # the URL may be a landing page, not the quoted text: unverified, not wrong
        if status == "missing" and is_publication and (ev.locator or "").lower() not in ("", "abstract", "title"):
            status = "no_text" if len(text or "") < 3000 else status
        rows.append(AuditRow(status=status, **base))
    return rows


def summarize(rows: list[AuditRow]) -> dict[str, int]:
    return dict(sorted(Counter(r.status for r in rows).items()))
