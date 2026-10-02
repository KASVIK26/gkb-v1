"""curator/graph/aicrp_postulation.py -- a parser, not a model: every claim is backed by the report's own row, whose name count it checks."""

from __future__ import annotations

from curator.graph.aicrp_postulation import EXTRACTOR, claim_specs, clean_name, gene_symbols, parse_tables
from curator.graph.quote_audit import check_quote
from curator.model import Entity
from curator.model.enums import EntityType

# Three tables in one document: the Sr table has a running page header inside a row, a starred name (different seed lot), a missing comma and
# a flagged check variety; the Yr table has the letter-only gene "yra" and a row whose count does not match its names.
REPORT = (
    "as discussed in table 2.8). Table 2.8. Sr genes in AVT entries during 2022-23 Sr-genes No. of lines Detail of lines "
    "Sr31+ 03 DBW443, HI1668, HD2967(c) "
    "Sr8a+11+2+ 04 HD2967(c), HD3086 (c), GW322(c)*, "
    "AICRP-W&B, Progress Report, Crop Protection, 2023 Page 56 "
    "PBW999 "
    "Sr7b+2+ 02 CG1036(i)(c), HD3086(c) "
    "Total 9 * different seed lot to that of previous cropping season "
    "Table 2.7 Yr genes in AVTlines during 2022-23 Yr-gene No. of lines Details of lines "
    "Yr2+ 03 HD2967(c), HD3086(c), HD3090(c) "
    "Yr9+a+ 02 HI1668, K2108 "
    "Yra+ 05 AKAW5104, AKAW5314, DBW394 "
    "Total 10 more prose"
)
ENTITIES = [
    Entity(id="var:wheat:HD2967", type=EntityType.VARIETY, name="HD 2967", crop="wheat"),
    Entity(id="var:wheat:HD3086", type=EntityType.VARIETY, name="HD 3086", crop="wheat"),
    Entity(id="var:wheat:GW322", type=EntityType.VARIETY, name="GW 322", crop="wheat"),
    Entity(id="gene:wheat:Sr2", type=EntityType.GENE, name="Sr2", crop="wheat", props={"symbol": "Sr2"}),
    Entity(id="gene:wheat:Sr11", type=EntityType.GENE, name="Sr11", crop="wheat", props={"symbol": "Sr11"}),
    Entity(id="gene:wheat:Yr2", type=EntityType.GENE, name="Yr2", crop="wheat", props={"symbol": "Yr2"}),
]


def test_gene_combinations_are_split_with_the_class_prefix_repeated():
    assert gene_symbols("sr8a+5+11+2+") == ("Sr8a", "Sr5", "Sr11", "Sr2")
    assert gene_symbols("yr9+a+") == ("Yr9", "Yra")
    assert gene_symbols("yra+") == ("Yra",)
    assert gene_symbols("lr13+10+3+") == ("Lr13", "Lr10", "Lr3")


def test_flags_are_trimmed_from_names():
    assert clean_name("dbw327 (c)") == "dbw327"
    assert clean_name("vl2041(i)(c)") == "vl2041"
    assert clean_name("gw322(c)*") == "gw322"


def test_rows_names_and_counts():
    rows = {(r.table, r.combo): r for r in parse_tables(REPORT)}
    sr = rows[("table 2.8", "sr8a+11+2+")]
    assert sr.entries == ("hd2967", "hd3086", "gw322", "pbw999") and sr.count == 4 and sr.count_ok   # the page header inside the row is cut out
    assert sr.seed_lot_changed == ("gw322",) and sr.genes == ("Sr8a", "Sr11", "Sr2")
    assert rows[("table 2.8", "sr31+")].entries == ("dbw443", "hi1668", "hd2967")
    assert rows[("table 2.7", "yra+")].genes == ("Yra",)
    assert not rows[("table 2.7", "yra+")].count_ok          # printed 05, three names: skipped, never guessed
    assert rows[("table 2.8", "sr31+")].table_total == 9


def test_a_mention_of_the_table_in_running_text_is_not_a_table():
    assert all(r.table != "table 2.9" for r in parse_tables("see table 2.9. Sr genes in AVT entries during 2022-23 and nothing else"))


def test_claims_only_for_known_varieties_with_the_method_stated_and_a_verifiable_quote():
    specs, new_genes, unknown, skipped = claim_specs(parse_tables(REPORT), source_id="doc:test_report", entities=ENTITIES)
    pairs = {(s["subject"], s["object"]) for s in specs}
    assert ("var:wheat:HD2967", "gene:wheat:Sr11") in pairs and ("var:wheat:HD3086", "gene:wheat:Yr2") in pairs
    assert not any(s["subject"] == "var:wheat:GW322" for s in specs)         # starred: a different seed lot, not used
    assert {g["id"] for g in new_genes} == {"gene:wheat:Sr31", "gene:wheat:Sr8a", "gene:wheat:Sr7b"}     # genes the KB lacks are created with only their symbol
    assert "dbw443" in unknown and "gw322" not in unknown
    assert len(skipped) == 1 and "yra+" in skipped[0]
    for spec in specs:
        assert spec["qualifiers"] == {"method": "postulation"}
        for ev in spec["evidence"]:
            assert ev["extractor"] == EXTRACTOR and ev["method"] == "postulation_pedigree"
            assert check_quote(ev["quote"], REPORT) in ("exact", "spacing")
