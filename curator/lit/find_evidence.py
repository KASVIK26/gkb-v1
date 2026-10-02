"""Find verbatim sentences / table rows where two things are mentioned together.

A curator asks "does any open-access paper say that variety X carries gene Y?" This searches Europe PMC for
papers that mention both, reads each open-access full text (prose and table rows), and returns only the exact
text in which both appear -- so every candidate quote is a real substring of a real paper, with its identifiers,
and nothing is paraphrased or generated. Deciding what that text MEANS (carries? is susceptible to? is merely
cited?) stays a human judgement; this only removes the searching and the transcription risk.

Name variants are matched loosely on spacing and hyphens ("HD 2932" = "HD2932" = "HD-2932") but never on
partial tokens ("Sr2" does not match "Sr24").
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass

from curator.lit import europepmc

_DOCTYPE_RE = re.compile(r"<!DOCTYPE[^>]*>", re.DOTALL)
_ABBREVIATIONS = ("et al", "Fig", "cv", "vs", "sp", "var", "No", "ca", "Tab", "Eq", "Ref")


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def term_pattern(term: str) -> re.Pattern[str]:
    """Regex for `term`, tolerant of spacing/hyphen differences but anchored on whole tokens."""
    parts = [re.escape(p) for p in re.split(r"[\s\-_]+", term.strip()) if p]
    loose = r"[\s\-]?".join(parts)
    # also tolerate "HD2932" for "HD 2932" at a letter/digit boundary inside one token
    loose = re.sub(r"(?<=[A-Za-z])(?=\d)", r"[\\s\\-]?", loose)
    return re.compile(rf"(?<![A-Za-z0-9]){loose}(?![A-Za-z0-9])", re.IGNORECASE)


def compile_term(term: str | re.Pattern[str]) -> re.Pattern[str]:
    """A name (matched loosely, see term_pattern) or an already-compiled regex used as given."""
    return term if isinstance(term, re.Pattern) else term_pattern(term)


def _any(patterns: Sequence[re.Pattern[str]], text: str) -> bool:
    return any(p.search(text) for p in patterns)


def split_sentences(text: str) -> list[str]:
    """Split on sentence ends, without breaking on 'et al.', 'Fig.', 'cv.', 'vs.' and similar."""
    protected = text
    for abbr in _ABBREVIATIONS:
        protected = re.sub(rf"\b({re.escape(abbr)})\.", "\\1\u2024", protected, flags=re.IGNORECASE)
    pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])", protected)
    return [_squash(p.replace("․", ".")) for p in pieces if p.strip()]


@dataclass(frozen=True)
class Hit:
    pmid: str | None
    pmcid: str | None
    doi: str | None
    title: str
    year: int | None
    journal: str | None
    locator: str  # "abstract", "body", or "Table N (row)"
    text: str  # verbatim sentence or table row

    @property
    def source_id(self) -> str:
        return f"pmid:{self.pmid}" if self.pmid else f"doi:{self.doi}"


def _body_paragraphs(root: ET.Element) -> list[str]:
    body = root.find(".//body")
    if body is None:
        return []
    return [_squash("".join(p.itertext())) for p in body.iter("p") if "".join(p.itertext()).strip()]


def _table_rows(root: ET.Element) -> list[tuple[str, str]]:
    """(locator, row text) for every table row; the caption is prefixed so a row keeps its context."""
    rows: list[tuple[str, str]] = []
    for wrap in root.iter("table-wrap"):
        label = _squash("".join(wrap.findtext("label") or "")) or "Table"
        for tr in wrap.iter("tr"):
            cells = [_squash("".join(c.itertext())) for c in tr if c.tag in ("td", "th")]
            text = " | ".join(c for c in cells if c)
            if text:
                rows.append((f"{label} (row)", text))
    return rows


def find_in_fulltext(xml_text: str, group_a: Sequence[str | re.Pattern[str]], group_b: Sequence[str | re.Pattern[str]]) -> list[tuple[str, str]]:
    """(locator, verbatim text) wherever any term of group_a and any term of group_b co-occur in one
    sentence or one table row. The reference list is never searched: a cited paper's finding is not
    this paper's own."""
    root = ET.fromstring(_DOCTYPE_RE.sub("", xml_text))
    a = [compile_term(t) for t in group_a]
    b = [compile_term(t) for t in group_b]
    found: list[tuple[str, str]] = []
    for abstract in root.iter("abstract"):
        for paragraph in (_squash("".join(p.itertext())) for p in abstract.iter("p")):
            for sentence in split_sentences(paragraph):
                if _any(a, sentence) and _any(b, sentence):
                    found.append(("abstract", sentence))
    for paragraph in _body_paragraphs(root):
        for sentence in split_sentences(paragraph):
            if _any(a, sentence) and _any(b, sentence):
                found.append(("body", sentence))
    for locator, row in _table_rows(root):
        if _any(a, row) and _any(b, row):
            found.append((locator, row))
    return found


def _query(group_a: Sequence[str], group_b: Sequence[str]) -> str:
    def clause(terms: Sequence[str]) -> str:
        return "(" + " OR ".join(f'"{t}"' for t in terms) + ")"

    return f"{clause(group_a)} AND {clause(group_b)}"


def find_evidence(group_a: Sequence[str], group_b: Sequence[str], *, max_papers: int = 15) -> list[Hit]:
    """Search Europe PMC for papers mentioning both groups and return their co-occurring text."""
    hits: list[Hit] = []
    a = [compile_term(t) for t in group_a]
    b = [compile_term(t) for t in group_b]
    for record in europepmc.search(_query(group_a, group_b), open_access_only=True, page_size=max_papers)[:max_papers]:
        meta = {
            "pmid": record.get("pmid"),
            "pmcid": record.get("pmcid"),
            "doi": record.get("doi"),
            "title": _squash(re.sub(r"<[^>]+>", "", record.get("title", ""))),
            "year": int(record["pubYear"]) if str(record.get("pubYear", "")).isdigit() else None,
            "journal": record.get("journalTitle"),
        }
        found: list[tuple[str, str]] = []
        xml_text = europepmc.fetch_fulltext_xml(record["pmcid"]) if record.get("pmcid") else None
        if xml_text:
            try:
                found = find_in_fulltext(xml_text, group_a, group_b)
            except ET.ParseError:
                xml_text = None
        if not xml_text and (record.get("pmid") or record.get("doi")):
            abstract = europepmc.fetch_abstract(f"pmid:{record['pmid']}" if record.get("pmid") else f"doi:{record['doi']}")
            if abstract:
                clean = _squash(re.sub(r"<[^>]+>", "", abstract))
                found = [("abstract", sent) for sent in split_sentences(clean) if _any(a, sent) and _any(b, sent)]
        seen: set[str] = set()
        for locator, text in found:
            if text not in seen:
                seen.add(text)
                hits.append(Hit(locator=locator, text=text, **meta))
    return hits
