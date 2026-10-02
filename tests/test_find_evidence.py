"""Unit tests for curator/lit/find_evidence.py -- synthetic JATS only, no network."""

from __future__ import annotations

from curator.lit.find_evidence import find_in_fulltext, split_sentences, term_pattern

JATS = """<?xml version="1.0"?>
<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Archiving and Interchange DTD v1.3 20210610//EN" "JATS-archivearticle1-3.dtd">
<article>
  <front><article-meta><abstract>
    <p>Cultivar HD 2932 carries Lr34 and Sr2. Other lines were also screened.</p>
  </abstract></article-meta></front>
  <body>
    <sec><title>Results</title>
      <p>As reported by Smith et al. 2010, PBW 343 possesses Lr26 on the 1BL.1RS translocation. HI 1544 lacked it.</p>
      <p>GW 322 was susceptible. Sr24 was absent from HD2932.</p>
      <table-wrap><label>Table 2</label><caption><p>Genes postulated</p></caption>
        <table><tbody>
          <tr><td>Cultivar</td><td>Genes</td></tr>
          <tr><td>HD-2932</td><td>Lr34, Sr2</td></tr>
          <tr><td>HI 1544</td><td>Lr13</td></tr>
        </tbody></table>
      </table-wrap>
    </sec>
  </body>
  <back><ref-list><ref><mixed-citation>HD 2932 Lr34 cited in a reference list</mixed-citation></ref></ref-list></back>
</article>"""


def _hits(a, b):
    return find_in_fulltext(JATS, a, b)


def test_finds_the_abstract_sentence_with_both_terms():
    hits = _hits(["HD 2932"], ["Lr34"])
    assert ("abstract", "Cultivar HD 2932 carries Lr34 and Sr2.") in hits


def test_matches_name_variants_loosely_on_spacing_and_hyphens():
    texts = [t for _, t in _hits(["HD 2932", "HD2932"], ["Sr2"])]
    assert any("Sr2." in t or "Sr2 " in t for t in texts)
    rows = [t for loc, t in _hits(["HD2932"], ["Lr34"]) if loc.startswith("Table")]
    assert rows == ["HD-2932 | Lr34, Sr2"]


def test_a_gene_name_does_not_match_a_longer_one():
    texts = [t for _, t in _hits(["HD 2932"], ["Sr2"])]
    assert not any("Sr24" in t and "Sr2," not in t and "Sr2." not in t and "Sr2 " not in t for t in texts)
    # "Sr24 was absent from HD2932" must not count as a mention of Sr2
    assert "Sr24 was absent from HD2932." not in texts


def test_et_al_does_not_split_a_sentence():
    texts = [t for _, t in _hits(["PBW 343"], ["Lr26"])]
    assert texts == ["As reported by Smith et al. 2010, PBW 343 possesses Lr26 on the 1BL.1RS translocation."]


def test_table_rows_are_returned_with_their_table_label():
    assert ("Table 2 (row)", "HI 1544 | Lr13") in _hits(["HI 1544"], ["Lr13"])


def test_the_reference_list_is_never_searched():
    assert not any("reference list" in t for _, t in _hits(["HD 2932"], ["Lr34"]))


def test_requires_both_groups_in_the_same_sentence():
    assert _hits(["GW 322"], ["Lr34"]) == []


def test_split_sentences_keeps_abbreviations_together():
    assert split_sentences("Cv. HD 2932 vs. HD 2967 was tested (Fig. 2). It resisted.") == [
        "Cv. HD 2932 vs. HD 2967 was tested (Fig. 2).",
        "It resisted.",
    ]


def test_term_pattern_is_anchored_on_whole_tokens():
    assert term_pattern("Lr34").search("carries Lr34, Sr2")
    assert not term_pattern("Lr34").search("Lr340 is unrelated")
    assert term_pattern("HD 2932").search("cultivar HD2932")


def test_a_name_with_a_hyphen_and_a_space_between_parts_is_found():
    assert term_pattern("PDKV- Kanak").search("101. PDKV- Kanak (AKG1303) 2021 Akola")
    assert term_pattern("PDKV Kanak").search("101. PDKV- Kanak (AKG1303)")
    assert not term_pattern("HD 29").search("HD 2932")  # whole tokens only


def test_en_dash_and_hyphen_are_the_same_separator_in_a_name():
    assert term_pattern("JS 20-29").search("JS 20\u201329 ... 2014")
    assert term_pattern("JS 20\u201329").search("JS 20-29")
