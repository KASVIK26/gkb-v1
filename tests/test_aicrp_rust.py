"""curator/graph/aicrp_rust.py -- a parser, not a model: every reading is backed by the row text it came from."""

from __future__ import annotations

import pytest

from curator.graph.aicrp_rust import SCALE, claim_specs, classify, parse_tables, reaction_of
from curator.graph.bundle import KGBundle
from curator.graph.quote_audit import check_quote
from curator.graph.variety_import import variety_bundle
from curator.graph.vocab_entities import reference_bundle

# "HS ACI" order (Table 9.2 style) and "ACI HS" order (Table 1.2 style) in one document, with a running page header in the
# middle of the second table, a footnote mark on a value, a trace score, a missing value and an infector line.
REPORT = (
    "Resistant entries (ACI<10) are listed here and more text. Entries with ACI up to 10.0 were categorized as resistant (Table 9.1). "
    "Table 9.2 Reactions of different entries of multiple diseases screening nursery 2021-22 against diseases "
    "S. No. Entries Stem rust Leaf rust (S) Leaf rust (N) Stripe rust LB (dd) ACI HS ACI HS ACI HS ACI HS Av HS "
    "1 HS 507 5S 2.4 20MS 7.5 30S 8.3 40S 10.3 34 57 "
    "2 HI 1544 10MR 1.8 20MS 4.1 10MR 0.7 100S 70.0 57 78 "
    "2a infector 80S 80.0 80S 80.0 80S 80.0 80S 80.0 "
    "3 HD 2864 5S 2.4 TS 0.1 ng 0.0 40S 8.3 34 57 "
    "and then some prose with a score >20 somewhere. Rust resistance materials in AVT (2022-23) with ACI upto 10.0 are given below: "
    "Table 1.2. Adult plant response of AVT entries against three rusts under epiphytotic conditions at hot spot locations in field during 2022-23 "
    "AVT No. Entry Stem rust Leaf rust (S) Leaf rust (N) Yellow rust Gene Postulation ACI HS ACI HS ACI HS ACI HS Sr Lr Yr "
    "1 MP 4010 (C) 15.8 40S 30.9 60S 42.3 60S 54.7 80S -* Lr13+1+* Yr9+ "
    "AICRP-W&B, Progress Report, Crop Protection, 2023 Page 17 "
    "AVT No. Entry Stem rust Leaf rust (S) Leaf rust (N) Yellow rust Gene Postulation ACI HS ACI HS ACI HS ACI HS Sr Lr Yr "
    "2 HI 1634 (C) 3.9 10MS 3.7 10S 8.8 60S* 67.5 80S -* R Yr2+ "
    "3 HI 8498 (C) 14.3 30MR 4.5 20MS 2.7 10S 12.8 60S Sr11+2+ Lr23+ - "
)


@pytest.fixture(scope="module")
def rows():
    return parse_tables(REPORT)


def test_reads_both_column_orders_by_the_shape_of_each_token(rows):
    by = {(r.table_title[:9], r.entry_clean): r for r in rows}
    hs_first = by[("table 9.2", "hi 1544")]
    assert [(v[0].rsplit(":", 1)[1], v[1], v[2], v[3]) for v in hs_first.values] == [
        ("stem_rust", None, "10mr", "1.8"), ("leaf_rust", "leaf rust (S) centres", "20ms", "4.1"),
        ("leaf_rust", "leaf rust (N) centres", "10mr", "0.7"), ("stripe_rust", None, "100s", "70.0")]
    aci_first = by[("table 1.2", "mp 4010")]
    assert [v[2] for v in aci_first.values] == ["40s", "60s", "60s", "80s"]
    assert aci_first.values[3][0] == "dis:wheat:stripe_rust"  # "Yellow rust" is stripe rust


def test_the_table_title_and_season_come_from_the_report(rows):
    assert {r.season for r in rows} == {"2021-22", "2022-23"}
    assert all(r.table_title.startswith("table ") for r in rows)


def test_a_page_header_and_a_repeated_column_header_mid_table_do_not_end_the_table(rows):
    names = [r.entry_clean for r in rows if r.table_title.startswith("table 1.2")]
    assert names == ["mp 4010", "hi 1634", "hi 8498"]


def test_footnote_marks_on_values_are_ignored(rows):
    hi1634 = next(r for r in rows if r.entry_clean == "hi 1634")
    assert hi1634.values[2][2] == "60s"


def test_infector_lines_are_not_entries(rows):
    assert all("infector" not in r.entry for r in rows)


def test_a_row_with_a_missing_value_is_skipped_not_guessed(rows):
    assert "hd 2864" not in {r.entry_clean for r in rows}  # "ng" in the third column


def test_only_the_response_letter_is_interpreted():
    assert [reaction_of(t) for t in ("10mr", "20ms", "5s", "r", "60s", "tr", "tms", "ts", "0", "ng")] == ["MR", "MS", "S", "R", "S", None, None, None, None, None]


def test_claims_are_made_only_for_varieties_the_kb_has_and_each_quote_is_verbatim():
    entities = KGBundle.merge(reference_bundle(), variety_bundle()).entities
    specs, unknown = claim_specs(parse_tables(REPORT), source_id="doc:test_report", entities=entities)
    ids = {s["subject"] for s in specs}
    assert ids == {"var:wheat:HI1544", "var:wheat:MP4010", "var:wheat:HI8498"} and "hs 507" in unknown and "hi 1634" in unknown
    reaction = next(s for s in specs if s["subject"] == "var:wheat:HI1544" and s["object"] == "dis:wheat:stripe_rust")
    assert reaction["qualifiers"] == {"reaction": "S", "stage": "adult", "season": "2021-22", "score_raw": "100S (ACI 70.0)", "scale": SCALE}
    for spec in specs:
        for ev in spec["evidence"]:
            assert ev["extractor"] == "parser:aicrp_rust@1" and check_quote(ev["quote"], REPORT) == "exact"


def test_leaf_rust_north_and_south_are_kept_apart():
    entities = KGBundle.merge(reference_bundle(), variety_bundle()).entities
    specs, _ = claim_specs(parse_tables(REPORT), source_id="doc:test_report", entities=entities)
    leaf = [s for s in specs if s["subject"] == "var:wheat:HI1544" and s["object"] == "dis:wheat:leaf_rust"]
    assert {s["qualifiers"]["location"] for s in leaf} == {"leaf rust (S) centres", "leaf rust (N) centres"}


def test_the_reports_own_aci_rule_decides_resistant_not_the_letter_of_the_worst_location():
    """Regression: `10S (ACI 2.7)` is resistant by the report's rule (ACI up to 10.0); the first parser called it susceptible and made ~100
    false conflicts with the variety notifications."""
    assert classify("10s", "2.7") == "R"
    assert classify("5s", "0.7") == "R"
    assert classify("40s", "17.0") == "S"
    assert classify("20ms", "12.0") == "MS"
    assert classify("40mr", "12.0") == "MR"
    assert classify("tr", "0.0") is None and classify("0", "0.0") is None


def test_the_row_in_the_pdf_that_read_as_susceptible_is_now_resistant():
    entities = KGBundle.merge(reference_bundle(), variety_bundle()).entities
    specs, _ = claim_specs(parse_tables(REPORT), source_id="doc:test_report", entities=entities)
    by = {(s["subject"], s["object"], s["qualifiers"].get("location")): s["qualifiers"]["reaction"] for s in specs if s["subject"] == "var:wheat:HI1544"}
    assert by[("var:wheat:HI1544", "dis:wheat:stem_rust", None)] == "R"           # 10MR, ACI 1.8
    assert by[("var:wheat:HI1544", "dis:wheat:leaf_rust", "leaf rust (S) centres")] == "R"   # 20MS, ACI 4.1: low infection overall
    assert by[("var:wheat:HI1544", "dis:wheat:stripe_rust", None)] == "S"          # 100S, ACI 70.0


def test_a_table_without_the_reports_rule_sentence_makes_no_claims():
    text = REPORT.replace("Entries with ACI up to 10.0 were categorized as resistant (Table 9.1).", "").replace(
        "Rust resistance materials in AVT (2022-23) with ACI upto 10.0 are given below:", "")
    entities = KGBundle.merge(reference_bundle(), variety_bundle()).entities
    specs, _ = claim_specs(parse_tables(text), source_id="doc:test_report", entities=entities)
    assert specs == []


def test_a_multi_year_status_table_is_not_read_as_a_single_season():
    """Table 1.4 prints one row per YEAR under each entry (2018-19, 2019-20, 2020-21 plus a mean); read as 'entry + 4 pairs' it gave wrong columns and seasons."""
    text = ("Entries with ACI up to 10.0 were categorized as resistant. "
            "Table 1.4: Status of disease resistance in AVT (final year entries) and check varieties during 2018-19, 2019-20 and 2020-21 "
            "S. No. Entry Stem rust Leaf rust (S) Leaf rust (N) Stripe rust ACI HS ACI HS ACI HS ACI HS "
            "1 HUW838 2018-19 6 20S 2.1 10MS 2.3 15S 7.5 20S 2019-20 2.4 10MS 2.6 15MS 8.1 50S 11.1 40S 2 DBW296 2018-19 6.7 20S 3 20S 4.4 15S 2.4 10S")
    assert parse_tables(text) == []
