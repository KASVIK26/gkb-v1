"""Crossref lookup for papers Europe PMC does not index (many Indian journals: Legume Research, Indian J. Agric. Sci., J. Oilseeds Res ...).

Crossref is a registry like PubMed: the DOI either resolves to a record or it does not, and the record's title is the one we store. It
carries no abstract and no full text, so the quote has to be found on the publisher's page (see candidates._verify_source); a quote that
cannot be found there is "unverifiable", never "verified".
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.crossref.org/works/"
_UA = {"User-Agent": "agrihub-kb/0.1 (research knowledge base; quote verification)"}


class CrossrefError(RuntimeError):
    """The Crossref API could not be reached or answered with something unusable."""


def get_work(doi: str, *, timeout: int = 30) -> dict | None:
    """The Crossref `message` for a DOI, or None when the DOI is not registered there (HTTP 404)."""
    request = urllib.request.Request(API + urllib.parse.quote(doi.strip(), safe="/"), headers=_UA)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8")).get("message")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise CrossrefError(f"Crossref answered HTTP {exc.code} for {doi}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        raise CrossrefError(f"Crossref unreachable for {doi}: {exc}") from exc


def title_of(work: dict) -> str:
    titles = work.get("title") or []
    return re.sub(r"<[^>]+>", "", titles[0]).strip() if titles else ""


def year_of(work: dict) -> int | None:
    for key in ("issued", "published-print", "published-online", "created"):
        parts = (work.get(key) or {}).get("date-parts") or [[None]]
        if parts[0] and parts[0][0]:
            return int(parts[0][0])
    return None


def venue_of(work: dict) -> str | None:
    containers = work.get("container-title") or []
    return containers[0].strip() if containers else (work.get("publisher") or None)


def pdf_links(work: dict) -> list[str]:
    return [l["URL"] for l in work.get("link") or [] if "pdf" in (l.get("content-type") or "").lower() and l.get("URL")]
