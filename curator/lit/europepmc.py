"""Europe PMC REST client: search, metadata verification, and full-text fetch.

This automates the exact manual step this project has performed by hand for every source that
went into ``kg/curated/*.yaml`` so far: look the identifier up on Europe PMC, confirm the real
title/journal/year/open-access status, and only then treat it as verified (see
``kg/curated/README.md``'s "Verifying a source" section and RESEARCH_ROADMAP.md Sec 5.1/5.2).

No fact is ever synthesised here -- every field returned comes straight from Europe PMC's own
response. A zero-hit search raises ``PublicationNotFound`` rather than returning something empty
that a caller might mistake for "verified".
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"
_USER_AGENT = "AgriHub-GKB-lit-pipeline/1 (+https://github.com/)"
_TIMEOUT_S = 30

_PMID_RE = re.compile(r"^pmid:(\d+)$")
_DOI_RE = re.compile(r"^doi:(\S+)$")


class EuropePMCError(RuntimeError):
    """Raised on an unexpected transport/response error (not a normal zero-hit search)."""


class PublicationNotFound(LookupError):
    """Raised when Europe PMC returns zero hits for an identifier that should be verifiable."""

    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"Europe PMC has no record for {identifier!r}")


@dataclass(frozen=True)
class VerifiedMetadata:
    """Real, Europe-PMC-confirmed bibliographic metadata for one publication.

    Field names deliberately mirror ``curator.model.claims.Source`` so a caller can build a
    ``Source(id=meta.id, type=SourceType.PUBLICATION, title=meta.title, year=meta.year,
    venue=meta.venue, verified=True)`` directly from this object.
    """

    id: str  # "pmid:<digits>" or "doi:<doi>" -- same string the caller passed in
    title: str
    year: int | None
    venue: str | None
    is_open_access: bool
    pmcid: str | None


def _http_get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise EuropePMCError(f"Europe PMC returned HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise EuropePMCError(f"Could not reach Europe PMC ({exc.reason}) for {url}") from exc
    except json.JSONDecodeError as exc:
        raise EuropePMCError(f"Europe PMC returned invalid JSON for {url}") from exc


def _http_get_text_or_none(url: str) -> str | None:
    """GET a URL as text, returning None (not raising) on a 404 -- a normal 'not available' case."""
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise EuropePMCError(f"Europe PMC returned HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise EuropePMCError(f"Could not reach Europe PMC ({exc.reason}) for {url}") from exc


def _search_url(query: str, *, result_type: str, page_size: int) -> str:
    params = {
        "query": query,
        "format": "json",
        "resultType": result_type,
        "pageSize": str(page_size),
    }
    return f"{BASE_URL}/search?{urllib.parse.urlencode(params)}"


def search(query: str, *, open_access_only: bool = True, page_size: int = 25) -> list[dict]:
    """Run a free-form Europe PMC query, returning raw hit dicts (Europe PMC's own field names).

    ``query`` should already be a well-formed Europe PMC query string (see
    ``curator.lit.query_builder.build_disease_queries`` for how one is constructed from the
    disease vocabulary). This function does not reshape or rename any field -- callers that need
    verified, typed metadata should use ``verify_publication`` instead.
    """
    full_query = f"({query}) AND OPEN_ACCESS:y" if open_access_only else query
    data = _http_get_json(_search_url(full_query, result_type="lite", page_size=page_size))
    return data.get("resultList", {}).get("result", [])


def get_record(identifier: str) -> dict:
    """Fetch the raw Europe PMC 'core' result dict for a pmid:/doi: identifier.

    Raises PublicationNotFound if Europe PMC has zero hits. Uses resultType=core so the same
    fetched record can supply both verified metadata (`verify_publication`) and the abstract
    text (`abstract_from_record`) from a single network call.
    """
    pmid_match = _PMID_RE.match(identifier)
    doi_match = _DOI_RE.match(identifier)
    if pmid_match:
        query = f"EXT_ID:{pmid_match.group(1)}"
    elif doi_match:
        query = f"DOI:{doi_match.group(1)}"
    else:
        raise ValueError(f"identifier must look like 'pmid:<digits>' or 'doi:<doi>', got {identifier!r}")

    data = _http_get_json(_search_url(query, result_type="core", page_size=1))
    results = data.get("resultList", {}).get("result", [])
    if not results:
        raise PublicationNotFound(identifier)
    return results[0]


def metadata_from_record(record: dict, identifier: str) -> VerifiedMetadata:
    """Build VerifiedMetadata from a record already fetched via get_record() -- avoids a second
    network round-trip when a caller needs both metadata and the abstract for the same paper."""
    year_raw = record.get("pubYear")
    return VerifiedMetadata(
        id=identifier,
        title=record.get("title", "").rstrip("."),
        year=int(year_raw) if year_raw else None,
        venue=record.get("journalTitle") or None,
        is_open_access=record.get("isOpenAccess") == "Y",
        pmcid=record.get("pmcid") or None,
    )


def verify_publication(identifier: str) -> VerifiedMetadata:
    """Look up `identifier` ("pmid:<digits>" or "doi:<doi>") and return its real metadata.

    This is the automated form of the manual check every source in kg/curated/ has gone through:
    "look the PMID up on Europe PMC and confirm the title matches before setting verified: true."
    """
    return metadata_from_record(get_record(identifier), identifier)


def abstract_from_record(record: dict) -> str | None:
    """Pull the abstract text out of a record already fetched via get_record()."""
    return record.get("abstractText") or None


def fetch_abstract(identifier: str) -> str | None:
    """Convenience wrapper: fetch a record and return its abstract (or None if it has none)."""
    return abstract_from_record(get_record(identifier))


def fetch_fulltext_xml(pmcid: str) -> str | None:
    """Fetch the JATS full-text XML for an open-access PMCID.

    Returns None (not an exception) when full text isn't available -- abstract-only is a normal,
    expected outcome for most papers, not an error condition.
    """
    url = f"{BASE_URL}/{pmcid}/fullTextXML"
    return _http_get_text_or_none(url)
