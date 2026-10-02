"""Unit tests for curator/graph/quote_audit.py -- the source text is injected, so no network."""

from __future__ import annotations

import re

from curator.graph.bundle import KGBundle
from curator.graph.quote_audit import audit_bundle, check_quote, normalise, summarize
from curator.model import Claim, Evidence, EvidenceMethod, Source, SourceType

ABSTRACT = "TestYr1 confers all-stage resistance to stripe rust — in wheat under “field” conditions."


def _bundle(quote: str | None, source_id: str = "pmid:1", locator: str = "abstract") -> KGBundle:
    claim = Claim(type="GENE_CONFERS_RESISTANCE", subject_id="gene:wheat:TestYr1", object_id="dis:wheat:stripe_rust",
                  qualifiers={"resistance_type": "ASR"})
    source = Source(id=source_id, type=SourceType.PUBLICATION, title="T", year=2020, verified=True) if source_id.startswith("pmid:") \
        else Source(id=source_id, type=SourceType.OFFICIAL_DOCUMENT, title="Doc", year=2020)
    ev = Evidence(claim_id=claim.id, source_id=source.id, method=EvidenceMethod.FIELD_MULTI_ENV, extractor="manual:t",
                  locator=locator, quote=quote)
    return KGBundle(sources=[source], claims=[claim], evidence=[ev])


def _status(quote, text, **kw):
    return audit_bundle(_bundle(quote, **kw), fetch=lambda _id: text)[0].status


def test_normalisation_ignores_case_whitespace_tags_dashes_and_curly_quotes():
    assert normalise("A  <i>b</i>–C “d”") == 'a b-c "d"'


def test_exact_quote_is_verified_despite_typography_differences():
    assert _status('TestYr1 confers all-stage resistance to stripe rust - in wheat under "field" conditions.', ABSTRACT) == "exact"


def test_fuzzy_quote_is_flagged_not_trusted():
    assert check_quote("TestYr1 confers all-stage resistance to stripe rusts in wheat under field conditions", ABSTRACT) == "fuzzy"


def test_fabricated_quote_is_missing():
    assert _status("The gene was cloned from barley and confers immunity to every rust race known.", ABSTRACT) == "missing"


def test_unreachable_source_is_no_text_not_a_failure():
    assert _status("TestYr1 confers all-stage resistance", None) == "no_text"


def test_full_text_only_quote_from_an_abstract_only_source_is_unverifiable_not_missing():
    assert _status("Seedlings were inoculated at the two-leaf stage with race 21E175.", ABSTRACT, locator="methods") == "no_text"


def test_rows_without_a_quote_and_non_publication_sources_are_not_checked():
    assert _status(None, ABSTRACT) == "no_quote"
    assert _status("anything at all in an official document", ABSTRACT, source_id="doc:release") == "not_checked"


def test_each_source_is_fetched_once():
    calls = []
    bundle = _bundle("TestYr1 confers all-stage resistance")
    bundle.evidence.append(bundle.evidence[0].model_copy(update={"locator": "abstract2"}))
    audit_bundle(bundle, fetch=lambda sid: calls.append(sid) or ABSTRACT)
    assert calls == ["pmid:1"]


def test_summarize_counts_statuses():
    assert summarize(audit_bundle(_bundle("TestYr1 confers all-stage resistance"), fetch=lambda _id: ABSTRACT)) == {"exact": 1}


def test_elided_quotes_are_checked_fragment_by_fragment_in_order():
    text = "Alpha beta gamma delta epsilon. Unrelated sentence here. Zeta eta theta iota kappa."
    assert check_quote("Alpha beta gamma delta epsilon...Zeta eta theta iota kappa.", text) == "exact"
    assert check_quote("Alpha beta gamma delta [and more] epsilon", text) == "exact"
    assert check_quote("Zeta eta theta iota kappa...Alpha beta gamma delta epsilon.", text) != "exact"  # wrong order
    assert check_quote("Alpha beta gamma delta epsilon...a fragment the paper never says anywhere", text) == "missing"


def test_html_escaped_titles_from_europe_pmc_are_unescaped():
    assert normalise("Resistance to &lt;i&gt;Phakopsora pachyrhizi&lt;/i&gt; in soybean") == "resistance to phakopsora pachyrhizi in soybean"


def test_official_documents_with_a_url_are_fetched_and_checked_by_url():
    bundle = _bundle("spray the crop with Propiconazole (Tilt) 25 EC @ 0.1 %", source_id="doc:icar_page")
    bundle.sources[0] = bundle.sources[0].model_copy(update={"url": "https://example.org/advisory"})
    fetched = []
    rows = audit_bundle(
        bundle, fetch=lambda _id: None,
        fetch_url=lambda url: fetched.append(url) or "If noticed, spray the crop with Propiconazole (Tilt) 25 EC @ 0.1 % (1 ml / litre).",
    )
    assert fetched == ["https://example.org/advisory"]
    assert rows[0].status == "exact"


def test_a_document_page_that_lacks_the_quote_is_not_on_page_rather_than_missing():
    bundle = _bundle("a sentence that is not on the landing page at all, honestly", source_id="doc:release")
    bundle.sources[0] = bundle.sources[0].model_copy(update={"url": "https://example.org/landing"})
    assert audit_bundle(bundle, fetch_url=lambda _u: "Some unrelated landing page text.")[0].status == "not_on_page"


def test_datasets_are_never_fetched_by_url():
    base = _bundle("computed alignment output")
    dataset = Source(id="ds:blast", type=SourceType.DATASET, title="BLAST", year=2026, url="https://example.org/x")
    ev = base.evidence[0].model_copy(update={"source_id": "ds:blast"})
    bundle = KGBundle(sources=[dataset], claims=base.claims, evidence=[ev])
    rows = audit_bundle(bundle, fetch_url=lambda _u: (_ for _ in ()).throw(AssertionError("fetched")))
    assert rows[0].status == "not_checked"


# ───────────────────────────── URL fetching: HTML, PDF and the Internet Archive fallback ─────────────────────────────
import json

import pytest

import curator.graph.quote_audit as qa

def _minimal_pdf(text: str) -> bytes:
    """A valid one-page PDF (with a real xref table) whose only content is `text`."""
    stream = f"BT /F1 12 Tf 10 50 Td ({text}) Tj ET".encode()
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 400 100]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length %d>>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    return out + b"trailer\n<</Root 1 0 R/Size %d>>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref_at)


def test_fetch_url_text_strips_html_scripts_and_tags(monkeypatch):
    monkeypatch.setattr(qa, "_read_url", lambda url: b"<html><script>var x=1;</script><p>Spray  <b>Tilt</b> now</p></html>")
    text = qa.fetch_url_text("https://example.org/page")
    assert "Spray Tilt now" in re.sub(r"\s+", " ", text) and "var x" not in text


def test_fetch_url_text_reads_pdfs(monkeypatch):
    pytest.importorskip("pypdf")
    monkeypatch.setattr(qa, "_read_url", lambda url: _minimal_pdf("Propiconazole 25 EC at 0.1 percent"))
    assert "Propiconazole 25 EC at 0.1 percent" in qa.fetch_url_text("https://example.org/doc.pdf")


def test_fetch_url_text_falls_back_to_the_internet_archive(monkeypatch):
    requested = []

    def fake_read(url):
        requested.append(url)
        if url.startswith("https://archive.org/wayback/available"):
            return json.dumps({"archived_snapshots": {"closest": {"url": "http://web.archive.org/web/20240701000000/https://x.gov.in/a.html"}}}).encode()
        if "20240701000000id_" in url:
            return b"<p>archived copy</p>"
        return None  # the live server is unreachable

    monkeypatch.setattr(qa, "_read_url", fake_read)
    assert "archived copy" in qa.fetch_url_text("https://x.gov.in/a.html")
    assert any("20240701000000id_/https://x.gov.in/a.html" in u for u in requested)


def test_fetch_url_text_is_none_when_neither_live_nor_archived(monkeypatch):
    monkeypatch.setattr(qa, "_read_url", lambda url: None)
    assert qa.fetch_url_text("https://x.gov.in/a.html") is None


def test_a_bare_less_than_sign_does_not_swallow_the_text_that_follows():
    """Regression: "(ACI<10)" on one page and ">20" on another once deleted every page in between from the audited text."""
    text = "Resistant entries (ACI<10) are listed. Table 1.2. Adult plant response of AVT entries. Entries with score >20 failed."
    n = normalise(text)
    assert "table 1.2. adult plant response of avt entries" in n and "failed" in n
    assert normalise("p < 0.05 and q <0.01, then x > 3") == "p < 0.05 and q <0.01, then x > 3"


def test_real_tags_are_still_removed():
    assert normalise("<p>Brandnew <i>Fusarium</i> 77</p><br/>was <b>resistant</b>") == "brandnew fusarium 77 was resistant"


def test_pdf_ligature_remnants_and_soft_hyphens_do_not_break_a_match():
    source = "Table 2.6: Bioforti" + chr(0) + "ed Wheat Varieties for Cen" + chr(0xAD) + "tral Zone"
    assert check_quote("Table 2.6: Biofortied Wheat Varieties for Central Zone", source) == "exact"


def test_a_word_split_by_the_pdf_is_verified_as_spacing_not_fuzzy():
    source = "83. GNG 2171 2017 Sriganga nagar ... tolerant to fusarium wilt disease"
    assert check_quote("83. GNG 2171 2017 Sriganganagar ... tolerant to fusarium wilt disease", source) == "spacing"
    assert check_quote("83. GNG 2171 2017 Sriganganagar ... tolerant to fusarium wilt disease", "83. GNG 2171 2017 Sriganganagar ... tolerant to fusarium wilt disease") == "exact"


def test_a_corrected_typo_is_not_spacing():
    """The source says "collor rot"; a quote that silently fixes it is not verbatim, whatever the spacing."""
    source = "mod. resistant to dry root rot, wilt &collor rot and tolerant to Ascochyta blight and BGM."
    assert check_quote("mod. resistant to dry root rot, wilt &collar rot and tolerant to Ascochyta blight and BGM.", source) == "fuzzy"


def test_a_table_row_quoted_as_short_cells_is_verified_when_the_cells_are_neighbours():
    source = "24 js 71 1991 मालवा क्षेत्र 25 js 75-46 1987 मध्य प्रदेश 26 पंत सोयाबीन 564 1991 उत्तरी"
    assert check_quote("JS 75–46 ... 1987 ... मध्य प्रदेश", source) == "exact"
    assert check_quote("JS 75-46 ... 1991 ... मध्य प्रदेश", source) == "missing"  # 1991 is not next to JS 75-46


def test_short_cells_far_apart_do_not_verify():
    filler = " lorem ipsum dolor sit amet" * 20
    source = "js 75-46" + filler + " 1987" + filler + " मध्य प्रदेश"
    assert check_quote("JS 75-46 ... 1987 ... मध्य प्रदेश", source) == "missing"


def test_every_occurrence_of_a_short_cell_is_tried():
    source = "20 js 95-60 2005 maharashtra 76 js 95-60 2007 मध्य प्रदेश 77"
    assert check_quote("JS 95-60 ... 2007 ... मध्य प्रदेश", source) == "exact"
