from curator.schema import CONFIDENCE_VALUES, NODE_LABELS, RELATIONSHIP_TYPES


def test_schema_has_expected_labels():
    assert NODE_LABELS["gene"] == "Gene"
    assert RELATIONSHIP_TYPES["gene_confers_resistance_to_disease"] == "CONFERS_RESISTANCE_TO"
    assert "High" in CONFIDENCE_VALUES
