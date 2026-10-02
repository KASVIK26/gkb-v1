"""Audit curated evidence: is every stored quote really in the source it cites?

The project's rule is that a fact is only as good as its verbatim quote, and the failure it guards against
is a plausible-looking citation that does not say what is claimed (RESEARCH_ROADMAP.md §2.2 D1/D2). This
re-fetches each cited paper from Europe PMC -- abstract, and the open-access full text including table rows
when there is one -- and checks every stored quote against it.

Statuses per evidence row:
  exact        the quote is a substring of the source text (after whitespace/quote/dash normalisation)
  spacing      identical to the source once whitespace is ignored (a PDF split a word); counts as verified
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
import http.client
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
    text = text.replace(chr(0), "").replace(chr(0xAD), "")  # PDF ligature remnants ("bioforti<NUL>ed") and soft hyphens
    text = re.sub(r"</?(?:i|b|em|strong|sub|sup|span|u)\b[^<>]*>", "", text)  # inline formatting: no gap
    # Block tags (p, h4, br...) separate words. A tag starts with a letter or "/" right after "<": a comparison such as
    # "ACI<10" or "p < 0.05" is text, and must not swallow everything up to the next ">" (it once deleted whole PDF tables).
    text = re.sub(r"</?[A-Za-z][^<>]*>|<!--.*?-->", " ", text)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"[‐-―−]", "-", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def _captions(root: ET.Element) -> list[str]:
    """Figure and table captions: real sentences of the paper (e.g. 'JG 62, the susceptible check, completely
    wilted...') that the plain-text body leaves out."""
    out = []
    for wrapper in list(root.iter("fig")) + list(root.iter("table-wrap")):
        caption = wrapper.find("caption")
        if caption is not None:
            out.append(_squash("".join(caption.itertext())))
    return out


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
                root = ET.fromstring(_DOCTYPE_RE.sub("", xml_text))
                parts.append(jats.extract_plain_text(xml_text))
                parts.extend(row for _, row in _table_rows(root))
                parts.extend(_captions(root))
            except ET.ParseError:
                pass
    return " ".join(p for p in parts if p)


_ELISION = re.compile(r"\.{3}|…|\[[^\]]*\]")  # "..." / "…" for cut text, [x] for an editorial insertion
MIN_FRAGMENT_CHARS = 12


def quote_fragments(quote: str) -> list[str]:
    """The verbatim stretches of a quote that a curator elided or edited with '...' or '[...]'."""
    pieces = [normalise(p) for p in _ELISION.split(quote)]
    long_pieces = [p for p in pieces if len(p) >= MIN_FRAGMENT_CHARS]
    if long_pieces:
        return long_pieces
    short_pieces = [p for p in pieces if p]
    return short_pieces if len(short_pieces) >= 2 else [normalise(quote)]  # table cells: see _all_short


def _all_short(quote: str) -> bool:
    """A quote made only of short pieces joined by '...' (a name, a year, a state: the cells of one table row)."""
    pieces = [normalise(p) for p in _ELISION.split(quote) if normalise(p)]
    return len(pieces) >= 2 and all(len(p) < MIN_FRAGMENT_CHARS for p in pieces)


SHORT_PIECE_WINDOW = 60  # characters allowed between consecutive short pieces: they must be neighbours, not coincidences


MAX_DOCUMENT_BYTES = 25_000_000
_USER_AGENT = {"User-Agent": "Mozilla/5.0 (agrihub-kb quote audit)"}


def _read_url(url: str) -> bytes | None:
    request = urllib.request.Request(url, headers=_USER_AGENT)
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return response.read(MAX_DOCUMENT_BYTES)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError, http.client.HTTPException):
        return None  # incl. a truncated download (IncompleteRead), which is not an OSError


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


def _in_order(fragments: list[str], text: str, *, window: int | None = None, position: int = 0) -> bool:
    """Each fragment appears after the previous one (and, if `window` is set, within that many characters of it).
    Every occurrence of a fragment is tried: "js 95-60" may appear on the page for two different states."""
    if not fragments:
        return True
    first, rest = fragments[0], fragments[1:]
    start = position
    while True:
        found = text.find(first, start)
        if found < 0:
            return False
        if (window is None or position == 0 or found - position <= window) and _in_order(rest, text, window=window, position=found + len(first)):
            return True
        start = found + 1


def check_quote(quote: str, source_text: str) -> str:
    """exact: every fragment appears verbatim, in order. spacing: identical once all whitespace is ignored (PDF text often
    splits a word: "sriganga naga"). fuzzy: each is very close but not identical. missing: neither."""
    text = normalise(source_text)
    fragments = quote_fragments(quote)
    window = SHORT_PIECE_WINDOW if _all_short(quote) else None
    if _in_order(fragments, text, window=window):
        return "exact"
    squashed = re.sub(r"\s+", "", text)
    if _in_order([re.sub(r"\s+", "", f) for f in fragments], squashed, window=window):
        return "spacing"
    if window is not None:
        return "missing"  # short cells carry too little text for an approximate match to mean anything
    return "fuzzy" if all(fuzz.partial_ratio(f, text) >= FUZZY_THRESHOLD for f in fragments) else "missing"


def explain_missing(quote: str, source_text: str) -> list[dict]:
    """Per fragment of `quote`: is it in the source, and if not, what is the closest passage there (with its score)?
    For humans (and prompt authors) -- the pass/fail decision is check_quote()."""
    text = normalise(source_text)
    out = []
    for fragment in quote_fragments(quote):
        found = fragment in text
        item = {"fragment": fragment, "found": found}
        if not found:
            alignment = fuzz.partial_ratio_alignment(fragment, text)
            if alignment is not None:
                item["closest_score"] = round(alignment.score)
                item["closest_text"] = text[alignment.dest_start: alignment.dest_end][:240]
        out.append(item)
    return out


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
