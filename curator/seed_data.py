"""Initial seed data for the AgriHub KB — 22 curated gene-disease edges."""

from __future__ import annotations

SEED_EDGES = [
    # Wheat stem rust resistance genes (Puccinia graminis)
    {
        "gene": {"id": "Sr33", "chromosome": "1B", "allele": "Sr33", "resistance_type": "APR"},
        "disease": {"name": "Stem Rust", "pathogen": "Puccinia graminis f. sp. tritici"},
        "varieties": [{"name": "Chinese Spring", "crop": "wheat"}],
        "confidence": "Very High",
        "source": "IWGSC RefSeq v2.1",
        "treatment": {"action": "Monitor for pustule development", "iot_trigger": None},
    },
    {
        "gene": {"id": "Sr35", "chromosome": "9B", "allele": "Sr35", "resistance_type": "All-stage"},
        "disease": {"name": "Stem Rust", "pathogen": "Puccinia graminis f. sp. tritici"},
        "varieties": [{"name": "Chinese Spring", "crop": "wheat"}],
        "confidence": "High",
        "source": "IWGSC RefSeq v2.1",
        "treatment": {"action": "Field monitoring", "iot_trigger": None},
    },
    {
        "gene": {"id": "Sr36", "chromosome": "2D", "allele": "Sr36", "resistance_type": "All-stage"},
        "disease": {"name": "Stem Rust", "pathogen": "Puccinia graminis f. sp. tritici"},
        "varieties": [{"name": "Chinese Spring", "crop": "wheat"}],
        "confidence": "Very High",
        "source": "IWGSC RefSeq v2.1",
        "treatment": {"action": "Monitor field conditions", "iot_trigger": None},
    },
    {
        "gene": {"id": "Sr39", "chromosome": "7B", "allele": "Sr39", "resistance_type": "APR"},
        "disease": {"name": "Stem Rust", "pathogen": "Puccinia graminis f. sp. tritici"},
        "varieties": [{"name": "Chinese Spring", "crop": "wheat"}],
        "confidence": "High",
        "source": "IWGSC RefSeq v2.1",
        "treatment": {"action": "Monitor for temperature changes", "iot_trigger": None},
    },
    # Wheat leaf rust resistance genes (Puccinia triticina)
    {
        "gene": {"id": "Lr18", "chromosome": "7D", "allele": "Lr18", "resistance_type": "All-stage"},
        "disease": {"name": "Leaf Rust", "pathogen": "Puccinia triticina"},
        "varieties": [{"name": "Chinese Spring", "crop": "wheat"}],
        "confidence": "Very High",
        "source": "IWGSC RefSeq v2.1",
        "treatment": {"action": "Monitor leaf for lesions", "iot_trigger": "high_humidity"},
    },
    {
        "gene": {"id": "Lr21", "chromosome": "5D", "allele": "Lr21", "resistance_type": "All-stage"},
        "disease": {"name": "Leaf Rust", "pathogen": "Puccinia triticina"},
        "varieties": [{"name": "Chinese Spring", "crop": "wheat"}],
        "confidence": "High",
        "source": "IWGSC RefSeq v2.1",
        "treatment": {"action": "Apply fungicide if needed", "iot_trigger": "high_humidity"},
    },
    {
        "gene": {"id": "Lr24", "chromosome": "3D", "allele": "Lr24", "resistance_type": "All-stage"},
        "disease": {"name": "Leaf Rust", "pathogen": "Puccinia triticina"},
        "varieties": [{"name": "Chinese Spring", "crop": "wheat"}],
        "confidence": "Very High",
        "source": "IWGSC RefSeq v2.1",
        "treatment": {"action": "Monitor leaf surface", "iot_trigger": "high_humidity"},
    },
    # Wheat stripe rust resistance genes (Puccinia striiformis)
    {
        "gene": {"id": "Yr18", "chromosome": "7D", "allele": "Yr18", "resistance_type": "APR"},
        "disease": {"name": "Stripe Rust", "pathogen": "Puccinia striiformis f. sp. tritici"},
        "varieties": [{"name": "Chinese Spring", "crop": "wheat"}],
        "confidence": "High",
        "source": "IWGSC RefSeq v2.1",
        "treatment": {"action": "Monitor for stripe patterns", "iot_trigger": "cool_temperature"},
    },
    {
        "gene": {"id": "Yr21", "chromosome": "2B", "allele": "Yr21", "resistance_type": "All-stage"},
        "disease": {"name": "Stripe Rust", "pathogen": "Puccinia striiformis f. sp. tritici"},
        "varieties": [{"name": "Chinese Spring", "crop": "wheat"}],
        "confidence": "Very High",
        "source": "IWGSC RefSeq v2.1",
        "treatment": {"action": "Field inspection", "iot_trigger": "cool_temperature"},
    },
    # Soybean disease resistance
    {
        "gene": {"id": "Rps1a", "chromosome": "3", "allele": "Rps1a", "resistance_type": "Race-specific"},
        "disease": {"name": "Phytophthora Root Rot", "pathogen": "Phytophthora sojae"},
        "varieties": [{"name": "Williams 82", "crop": "soybean"}],
        "confidence": "High",
        "source": "USDA-ARS SoyBase",
        "treatment": {"action": "Manage soil moisture", "iot_trigger": "high_soil_moisture"},
    },
    {
        "gene": {"id": "Rps6", "chromosome": "3", "allele": "Rps6", "resistance_type": "Race-specific"},
        "disease": {"name": "Phytophthora Root Rot", "pathogen": "Phytophthora sojae"},
        "varieties": [{"name": "Williams 82", "crop": "soybean"}],
        "confidence": "High",
        "source": "USDA-ARS SoyBase",
        "treatment": {"action": "Improve drainage", "iot_trigger": "high_soil_moisture"},
    },
    {
        "gene": {"id": "Scn3", "chromosome": "11", "allele": "Scn3", "resistance_type": "Quantitative"},
        "disease": {"name": "Soybean Cyst Nematode", "pathogen": "Heterodera glycines"},
        "varieties": [{"name": "Williams 82", "crop": "soybean"}],
        "confidence": "Medium",
        "source": "USDA-ARS SoyBase",
        "treatment": {"action": "Monitor root systems", "iot_trigger": None},
    },
    # Chickpea disease resistance
    {
        "gene": {"id": "Ca_LG3_10250", "chromosome": "Ca3", "allele": "wildtype", "resistance_type": "Quantitative"},
        "disease": {"name": "Ascochyta Blight", "pathogen": "Ascochyta rabiei"},
        "varieties": [{"name": "ICC4958", "crop": "chickpea"}],
        "confidence": "High",
        "source": "ICRISAT BGI v2019",
        "treatment": {"action": "Monitor leaf symptoms", "iot_trigger": "high_humidity"},
    },
    {
        "gene": {"id": "Ca_LG1_5420", "chromosome": "Ca1", "allele": "resistant", "resistance_type": "Qualitative"},
        "disease": {"name": "Fusarium Wilt", "pathogen": "Fusarium oxysporum"},
        "varieties": [{"name": "ICC4958", "crop": "chickpea"}],
        "confidence": "High",
        "source": "ICRISAT BGI v2019",
        "treatment": {"action": "Use resistant rootstock", "iot_trigger": None},
    },
    {
        "gene": {"id": "Ca_LG5_8901", "chromosome": "Ca5", "allele": "resistant", "resistance_type": "Qualitative"},
        "disease": {"name": "Botrytis Gray Mold", "pathogen": "Botrytis cinerea"},
        "varieties": [{"name": "ICC4958", "crop": "chickpea"}],
        "confidence": "Medium",
        "source": "ICRISAT BGI v2019",
        "treatment": {"action": "Improve air circulation", "iot_trigger": "high_humidity"},
    },
    # Additional wheat resistance genes
    {
        "gene": {"id": "Pm3b", "chromosome": "1A", "allele": "Pm3b", "resistance_type": "All-stage"},
        "disease": {"name": "Powdery Mildew", "pathogen": "Blumeria graminis f. sp. tritici"},
        "varieties": [{"name": "Chinese Spring", "crop": "wheat"}],
        "confidence": "Very High",
        "source": "IWGSC RefSeq v2.1",
        "treatment": {"action": "Monitor for white coating", "iot_trigger": None},
    },
    {
        "gene": {"id": "Ml26", "chromosome": "6A", "allele": "Ml26", "resistance_type": "All-stage"},
        "disease": {"name": "Powdery Mildew", "pathogen": "Blumeria graminis f. sp. tritici"},
        "varieties": [{"name": "Chinese Spring", "crop": "wheat"}],
        "confidence": "High",
        "source": "IWGSC RefSeq v2.1",
        "treatment": {"action": "Inspect leaves weekly", "iot_trigger": None},
    },
    # Additional soybean resistance genes
    {
        "gene": {"id": "Rst", "chromosome": "19", "allele": "Rst", "resistance_type": "Quantitative"},
        "disease": {"name": "Sudden Death Syndrome", "pathogen": "Fusarium virguliforme"},
        "varieties": [{"name": "Williams 82", "crop": "soybean"}],
        "confidence": "Medium",
        "source": "USDA-ARS SoyBase",
        "treatment": {"action": "Monitor root rot symptoms", "iot_trigger": None},
    },
    # Additional chickpea resistance genes
    {
        "gene": {"id": "Ca_LG2_12500", "chromosome": "Ca2", "allele": "resistant", "resistance_type": "Qualitative"},
        "disease": {"name": "Root Rot", "pathogen": "Rhizoctonia solani"},
        "varieties": [{"name": "ICC4958", "crop": "chickpea"}],
        "confidence": "High",
        "source": "ICRISAT BGI v2019",
        "treatment": {"action": "Ensure good drainage", "iot_trigger": None},
    },
    {
        "gene": {"id": "Ca_LG4_7350", "chromosome": "Ca4", "allele": "wildtype", "resistance_type": "Quantitative"},
        "disease": {"name": "Anthracnose", "pathogen": "Colletotrichum truncatum"},
        "varieties": [{"name": "ICC4958", "crop": "chickpea"}],
        "confidence": "Medium",
        "source": "ICRISAT BGI v2019",
        "treatment": {"action": "Prune infected tissue", "iot_trigger": "high_humidity"},
    },
    {
        "gene": {"id": "Fhb1", "chromosome": "3B", "allele": "Fhb1", "resistance_type": "Quantitative"},
        "disease": {"name": "Fusarium Head Blight", "pathogen": "Fusarium graminearum"},
        "varieties": [{"name": "Chinese Spring", "crop": "wheat"}],
        "confidence": "High",
        "source": "IWGSC RefSeq v2.1",
        "treatment": {"action": "Monitor spike development", "iot_trigger": None},
    },
    {
        "gene": {"id": "Cre8", "chromosome": "5", "allele": "Cre8", "resistance_type": "Qualitative"},
        "disease": {"name": "Cyst Nematode", "pathogen": "Heterodera cyst"},
        "varieties": [{"name": "Williams 82", "crop": "soybean"}],
        "confidence": "Medium",
        "source": "USDA-ARS SoyBase",
        "treatment": {"action": "Rotate crops", "iot_trigger": None},
    },
]

assert len(SEED_EDGES) == 22, f"Expected 22 seed edges, got {len(SEED_EDGES)}"
