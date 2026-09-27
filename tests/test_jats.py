"""Tests for curator/lit/jats.py -- turning raw JATS XML into clean plain text.

Uses a small synthetic JATS snippet, not a real fetched paper, so this suite has no network
dependency. The real paper (pmid:30140185) that motivated this module is exercised live in the
Phase 6 full-paper test (PHASES.md item 33), not here.
"""

from __future__ import annotations

from curator.lit.jats import extract_plain_text

_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Archiving and Interchange DTD v1.4//EN" "JATS.dtd">
<article>
  <front>
    <article-meta>
      <title-group><article-title>A Test Paper About TestGene1</article-title></title-group>
      <abstract><p>TestGene1 confers resistance to test rust in wheat.</p></abstract>
    </article-meta>
  </front>
  <body>
    <sec>
      <title>Introduction</title>
      <p>Test rust is a major disease of wheat <xref ref-type="bibr" rid="R1">1</xref>.</p>
    </sec>
    <sec>
      <title>Results</title>
      <sec>
        <title>Field trials</title>
        <p>TestGene1 reduced disease severity by 80 percent across three seasons.</p>
      </sec>
      <sec>
        <title>Molecular analysis</title>
        <p>TestGene1 encodes a protein of unknown function.</p>
      </sec>
    </sec>
  </body>
  <back>
    <ref-list>
      <ref id="R1"><mixed-citation>Someone et al. 2010. A citation that must not appear in the output.</mixed-citation></ref>
    </ref-list>
  </back>
</article>
"""


def test_extracts_title_and_abstract():
    text = extract_plain_text(_SAMPLE)
    assert "A Test Paper About TestGene1" in text
    assert "TestGene1 confers resistance to test rust in wheat." in text


def test_extracts_body_sections_in_order():
    text = extract_plain_text(_SAMPLE)
    intro_idx = text.index("Test rust is a major disease of wheat")
    trials_idx = text.index("TestGene1 reduced disease severity")
    molecular_idx = text.index("TestGene1 encodes a protein")
    assert intro_idx < trials_idx < molecular_idx


def test_preserves_nested_section_titles():
    text = extract_plain_text(_SAMPLE)
    assert "Field trials" in text
    assert "Molecular analysis" in text


def test_excludes_reference_list():
    text = extract_plain_text(_SAMPLE)
    assert "Someone et al. 2010" not in text
    assert "A citation that must not appear in the output" not in text


def test_keeps_inline_citation_markers_in_body_text():
    # The reference LIST is excluded, but an inline citation marker within a real sentence stays --
    # the model still needs to see "as reported by X [1]" to correctly identify it as a citation
    # (claim_extraction_v1.md's own Rule 3), rather than the marker vanishing and looking like a
    # first-hand claim.
    text = extract_plain_text(_SAMPLE)
    assert "Test rust is a major disease of wheat" in text


def test_handles_missing_body_gracefully():
    minimal = """<article><front><article-meta>
        <title-group><article-title>No Body Paper</article-title></title-group>
    </article-meta></front></article>"""
    text = extract_plain_text(minimal)
    assert "No Body Paper" in text
