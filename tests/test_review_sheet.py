"""Batch review by spreadsheet: sheet -> filled CSV -> apply (sample gate, reviewer stamps, held-back rows)."""

from __future__ import annotations

import csv
import json

import pytest

from curator.graph.bundle import KGBundle
from curator.graph.kg_files import load_curated_file
from curator.graph.scoring import score_bundle
from curator.graph.variety_import import variety_bundle
from curator.graph.vocab_entities import reference_bundle
from curator.lit.candidates import process_candidates, to_curated_yaml
from curator.lit.review_sheet import ReviewError, apply_review, make_sheet, sample_size

NAMES = ["Alpha 11", "Bravo 22", "Charlie 33", "Delta 44", "Echo 55", "Foxtrot 66", "Golf 77", "Hotel 88", "India 99", "Juliet 12", "Kilo 34", "Lima 56"]
RECORD = {"pmid": "99999002", "doi": "10.1000/t2", "title": "Leaf rust reactions of new lines.", "pubYear": "2024", "journalTitle": "Test Journal",
          "pubTypeList": {"pubType": ["Journal Article"]}}
TEXT = " ".join(f"The variety {n} was resistant to leaf rust." for n in NAMES) + " Filler text. " * 300
ADVISORY_TEXT = " For yellow rust control spray Propiconazole 25 EC at 0.1% when the disease is first noticed."


@pytest.fixture(scope="module")
def bundle() -> KGBundle:
    return KGBundle.merge(reference_bundle(), variety_bundle())


def _candidates(with_advisory: bool = False) -> list[str]:
    base = {"producer": "test", "batch_id": "wo-test", "crop": "wheat", "claim_type": "VARIETY_REACTION", "object": {"text": "leaf rust", "type": "Disease"},
            "qualifiers": {"reaction": "R", "stage": "adult"}, "source": {"kind": "publication", "pmid": "99999002", "title": "Leaf rust reactions of new lines"},
            "locator": "Results", "evidence_basis": "primary_field"}
    lines = [json.dumps({**base, "candidate_id": f"T-{i:02d}", "subject": {"text": n, "type": "Variety"}, "quote": f"The variety {n} was resistant to leaf rust."})
             for i, n in enumerate(NAMES)]
    if with_advisory:
        lines.append(json.dumps({**base, "candidate_id": "T-ADV", "claim_type": "DISEASE_MANAGED_BY", "qualifiers": {}, "evidence_basis": "review_or_secondary",
                                 "subject": {"text": "yellow rust", "type": "Disease"},
                                 "object": {"text": "Propiconazole spray", "type": "Advisory", "advisory": {"action_type": "chemical", "active_ingredient": "Propiconazole 25 EC", "dose": "0.1%", "timing": "when the disease is first noticed"}},
                                 "quote": "For yellow rust control spray Propiconazole 25 EC at 0.1% when the disease is first noticed"}))
    return lines


@pytest.fixture()
def batch(bundle, tmp_path):
    result = process_candidates(_candidates(with_advisory=True), bundle=bundle, fetch_record=lambda _i: RECORD,
                                fetch_text=lambda _i: TEXT + ADVISORY_TEXT, fetch_url=lambda _u: None)
    assert result.counts() == {"accepted": 13}
    path = tmp_path / "batch.yaml"
    path.write_text(to_curated_yaml(result, "test"), encoding="utf-8")
    return path


def _fill(sheet_path, verdict="OK", **overrides):
    """Fill every row (like a reviewer who ticked everything), then apply per-row overrides by row_id."""
    with sheet_path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["verdict"] = verdict
        r.update(overrides.get(r["row_id"], {}))
    with sheet_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def test_sample_size_is_ten_or_ten_percent():
    assert sample_size(4) == 4 and sample_size(50) == 10 and sample_size(400) == 40


def test_sheet_describes_each_claim_in_plain_words_with_a_clickable_source(batch, bundle, tmp_path):
    sheet = tmp_path / "s.csv"
    counts = make_sheet(batch, bundle, sheet)
    assert counts == {"rows": 13, "sample": 10}
    rows = list(csv.DictReader(sheet.open(encoding="utf-8-sig", newline="")))
    adv = next(r for r in rows if r["claim_type"] == "DISEASE_MANAGED_BY")
    assert "Propiconazole 25 EC" in adv["advisory_product_dose_timing"] and "0.1%" in adv["advisory_product_dose_timing"]
    reaction = next(r for r in rows if r["claim_type"] == "VARIETY_REACTION")
    assert " is R to Leaf rust" in reaction["the_claim_in_words"]
    assert reaction["source_link"].startswith("https://")
    assert rows[0]["in_sample"] == "YES"  # sample rows come first


def test_a_passing_review_stamps_reviewers_and_removes_the_model_discount(batch, bundle, tmp_path):
    sheet, out = tmp_path / "s.csv", tmp_path / "out.yaml"
    make_sheet(batch, bundle, sheet)
    _fill(sheet)
    result = apply_review(batch, sheet, out, reviewer="Dr Patil")
    assert (result.accepted_claims, result.reviewed_claims, len(result.held)) == (13, 13, 0)
    loaded = load_curated_file(out)
    assert {ev.reviewer for ev in loaded.evidence} == {"Dr Patil"} and all(c.status.value == "reviewed" for c in loaded.claims)
    scored = score_bundle(KGBundle.merge(bundle, loaded), as_of_year=2026)
    claim = next(c for c in scored.claims if c.subject_id == "var:wheat:ALPHA11")
    assert claim.score == pytest.approx(0.5)  # field_single_env 0.5, no x0.6 once a person has reviewed it


def test_unreviewed_rows_stay_unreviewed_and_keep_the_discount(batch, bundle, tmp_path):
    sheet, out = tmp_path / "s.csv", tmp_path / "out.yaml"
    make_sheet(batch, bundle, sheet)
    rows = _fill(sheet, verdict="OK")
    outside = next(r["row_id"] for r in rows if r["in_sample"] != "YES")
    _fill(sheet, verdict="OK", **{outside: {"verdict": ""}})
    apply_review(batch, sheet, out, reviewer="Dr Patil")
    loaded = load_curated_file(out)
    unreviewed = [c for c in loaded.claims if c.status.value == "unreviewed"]
    assert len(unreviewed) == 1


def test_batch_is_refused_while_a_sample_row_has_no_verdict(batch, bundle, tmp_path):
    sheet = tmp_path / "s.csv"
    make_sheet(batch, bundle, sheet)
    rows = _fill(sheet, verdict="OK")
    first_sample = next(r["row_id"] for r in rows if r["in_sample"] == "YES")
    _fill(sheet, verdict="OK", **{first_sample: {"verdict": ""}})
    with pytest.raises(ReviewError, match="no verdict"):
        apply_review(batch, sheet, tmp_path / "out.yaml", reviewer="x")
    assert not (tmp_path / "out.yaml").exists()


def test_one_unconfirmed_row_in_a_sample_of_ten_fails_the_batch(batch, bundle, tmp_path):
    sheet = tmp_path / "s.csv"
    make_sheet(batch, bundle, sheet)
    rows = _fill(sheet, verdict="OK")
    victim = next(r["row_id"] for r in rows if r["in_sample"] == "YES")
    _fill(sheet, verdict="OK", **{victim: {"verdict": "UNSURE"}})  # UNSURE counts against the batch
    with pytest.raises(ReviewError, match="batch rejected"):
        apply_review(batch, sheet, tmp_path / "out.yaml", reviewer="x")
    assert not (tmp_path / "out.yaml").exists()


def test_wrong_rows_outside_the_sample_are_held_back_not_published(batch, bundle, tmp_path):
    sheet, out = tmp_path / "s.csv", tmp_path / "out.yaml"
    make_sheet(batch, bundle, sheet)
    rows = _fill(sheet, verdict="OK")
    outside = next(r["row_id"] for r in rows if r["in_sample"] != "YES")
    _fill(sheet, verdict="OK", **{outside: {"verdict": "WRONG", "comment": "table is for a different crop"}})
    result = apply_review(batch, sheet, out, reviewer="x")
    assert result.accepted_claims == 12 and [h["row_id"] for h in result.held] == [outside]
    assert result.held[0]["comment"] == "table is for a different crop"


def test_an_advisory_that_does_not_fit_the_region_is_held_back(batch, bundle, tmp_path):
    sheet, out = tmp_path / "s.csv", tmp_path / "out.yaml"
    make_sheet(batch, bundle, sheet, everything=True)
    _fill(sheet, verdict="OK", **{"T-ADV": {"local_fit": "NO", "comment": "dose is for hills, not Malwa"}})
    result = apply_review(batch, sheet, out, reviewer="x")
    assert [h["row_id"] for h in result.held] == ["T-ADV"]
    assert all(c.type.value != "DISEASE_MANAGED_BY" for c in load_curated_file(out).claims)


def test_ok_without_any_reviewer_name_is_refused(batch, bundle, tmp_path):
    sheet = tmp_path / "s.csv"
    make_sheet(batch, bundle, sheet)
    _fill(sheet)
    with pytest.raises(ReviewError, match="reviewer name"):
        apply_review(batch, sheet, tmp_path / "out.yaml")


def test_a_mistyped_verdict_is_refused(batch, bundle, tmp_path):
    sheet = tmp_path / "s.csv"
    make_sheet(batch, bundle, sheet)
    _fill(sheet, verdict="yes")
    with pytest.raises(ReviewError, match="not one of OK"):
        apply_review(batch, sheet, tmp_path / "out.yaml", reviewer="x")
