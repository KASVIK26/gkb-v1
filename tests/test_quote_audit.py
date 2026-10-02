"""Unit tests for curator/graph/quote_audit.py -- the source text is injected, so no network."""

from __future__ import annotations

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
