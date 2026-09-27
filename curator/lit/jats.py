"""Turn Europe PMC's raw JATS full-text XML into clean, section-labeled plain text.

Before this module existed, `curator.lit.run_extraction.extract_paper` sent Europe PMC's raw
`fetch_fulltext_xml()` result -- untouched `<article>` tag soup -- straight to the LLM whenever full
text was used. None of this session's 5 pilot papers were open access, so this was never exercised
until a real full-paper test (PHASES.md item 33) fetched `pmid:30140185` and found 134,698 characters
of raw XML about to be sent as "source text". This is RESEARCH_ROADMAP.md's own still-open task 5.3
("JATS parser -> sections + tables"), scoped here to sections only (full table extraction stays task
5.9, out of scope) -- enough to make full-text extraction meaningful rather than noise.

Real JATS documents nest sections (`<sec><title/><p/>*<sec>...</sec>*</sec>`), so this walks the tree
recursively rather than assuming a flat structure. The reference list (`<back><ref-list>`) is
deliberately excluded: a citation to another paper is never this paper's own finding, per every
extraction prompt's own Rule 3, and reference lists are pure noise for that purpose.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

_DOCTYPE_RE = re.compile(r"<!DOCTYPE[^>]*>", re.DOTALL)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _section_lines(sec: ET.Element, *, depth: int = 1) -> list[str]:
    """Recursively render one <sec>: its own title, direct paragraphs, then nested <sec>s in order."""
    lines: list[str] = []
    title_el = sec.find("title")
    if title_el is not None:
        heading = _clean("".join(title_el.itertext()))
        if heading:
            lines.append(f"{'#' * min(depth + 1, 6)} {heading}")

    for child in sec:
        if child.tag == "p":
            para = _clean("".join(child.itertext()))
            if para:
                lines.append(para)
        elif child.tag == "sec":
            lines.extend(_section_lines(child, depth=depth + 1))
        # table-wrap, fig, boxed-text, etc. are deliberately skipped this pass (roadmap task 5.9).

    return lines


def extract_plain_text(xml_text: str) -> str:
    """Parse JATS XML into clean plain text: title, abstract, then body sections in reading order.
    Excludes the reference list. Raises ET.ParseError on genuinely malformed XML -- callers should
    treat that the same as "no full text available" rather than send unparseable input to an LLM."""
    cleaned_xml = _DOCTYPE_RE.sub("", xml_text)
    root = ET.fromstring(cleaned_xml)

    lines: list[str] = []

    title_el = root.find(".//article-title")
    if title_el is not None:
        title = _clean("".join(title_el.itertext()))
        if title:
            lines.append(f"# {title}")

    abstract_el = root.find(".//abstract")
    if abstract_el is not None:
        abstract_text = _clean("".join(abstract_el.itertext()))
        if abstract_text:
            lines.append("## Abstract")
            lines.append(abstract_text)

    body = root.find("body")
    if body is not None:
        for child in body:
            if child.tag == "sec":
                lines.extend(_section_lines(child))
            elif child.tag == "p":
                para = _clean("".join(child.itertext()))
                if para:
                    lines.append(para)

    return "\n\n".join(lines)
