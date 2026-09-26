# KG v1 scope

Frozen 2026-09-25. Change it only by editing this file and `config/vocab/*.yaml` together.

## Crops and priority diseases (17 IDs; your 15 with the wheat rusts split into 3)

| Crop | Disease (ID) | Pathogen | Type | IoT coupling |
|---|---|---|---|---|
| Soybean | Rust (`dis:soybean:rust`) | *Phakopsora pachyrhizi* | foliar, airborne | proxy (leaf wetness) |
| Soybean | Charcoal rot (`dis:soybean:charcoal_rot`) | *Macrophomina phaseolina* | soil-borne | **direct** (soil temperature and moisture) |
| Soybean | Frogeye leaf spot (`dis:soybean:frogeye_leaf_spot`) | *Cercospora sojina* | foliar | proxy |
| Soybean | Anthracnose (`dis:soybean:anthracnose`) | *Colletotrichum truncatum* | foliar/pod, seed-borne | proxy |
| Soybean | Pod and stem blight (`dis:soybean:pod_stem_blight`) | *Diaporthe phaseolorum* var. *sojae* | stem/pod, seed-borne | proxy |
| Soybean | Rhizoctonia root rot (`dis:soybean:rhizoctonia_root_rot`) | *Rhizoctonia solani* | soil-borne | **direct** |
| Soybean | Bacterial pustule (`dis:soybean:bacterial_pustule`) | *Xanthomonas citri* pv. *glycines* | foliar, bacterial | proxy (rain) |
| Soybean | Soybean mosaic (`dis:soybean:mosaic_virus`) | SMV (potyvirus; aphids, seed) | systemic, virus | indirect |
| Wheat | Stripe/yellow rust (`dis:wheat:stripe_rust`) | *P. striiformis* f. sp. *tritici* | foliar | proxy |
| Wheat | Leaf/brown rust (`dis:wheat:leaf_rust`) | *P. triticina* | foliar | proxy |
| Wheat | Stem/black rust (`dis:wheat:stem_rust`) | *P. graminis* f. sp. *tritici* | foliar/stem | proxy |
| Wheat | Powdery mildew (`dis:wheat:powdery_mildew`) | *Blumeria graminis* f. sp. *tritici* | foliar | **direct** (RH, temperature) |
| Wheat | Fusarium head blight (`dis:wheat:fusarium_head_blight`) | *F. graminearum* species complex | spike | proxy |
| Chickpea | Fusarium wilt (`dis:chickpea:fusarium_wilt`) | *F. oxysporum* f. sp. *ciceris* | soil-borne, vascular | **direct** |
| Chickpea | Dry root rot (`dis:chickpea:dry_root_rot`) | *Macrophomina phaseolina* | soil-borne | **direct** |
| Chickpea | Collar rot (`dis:chickpea:collar_rot`) | *Athelia* (*Sclerotium*) *rolfsii* | soil-borne | **direct** |
| Chickpea | Rust (`dis:chickpea:rust`) | *Uromyces ciceris-arietini* | foliar | proxy |

"Wheat rusts" are modelled as **three diseases** grouped under `dis:wheat:rusts`. They have different pathogens,
different resistance-gene families (Yr / Lr / Sr), different pathotypes and different temperature optima, so one
"rust" node would give wrong answers.

**Worth noting for the research story:** 5 of the 17 diseases are soil-borne, and the device's soil probe measures
their main drivers directly. Charcoal rot (soybean) and dry root rot (chickpea) share one pathogen,
*M. phaseolina*. In the soybean (kharif) to chickpea (rabi) rotation common in central India, that inoculum
carries over, which gives the KG a cross-crop link to exploit.

## Growth stages

Sowing to harvest for all three crops, plus pre-sowing and post-harvest system stages. See
`config/vocab/growth_stages.yaml`. Internal code: BBCH. Display: Zadoks (wheat), Fehr & Caviness (soybean),
CP phenophases (chickpea).

## Sensors

Fixed AgriNode hardware (SN-3002 soil probe, AHT20, BME280, VEML7700, SD3031 RTC). See
`config/vocab/sensors.yaml` and `docs/interfaces.md`.

## Geography (decided 2026-09-25)

| Priority | Region | Notes |
|---|---|---|
| **Primary** | **Malwa plateau, Madhya Pradesh, centred on Indore** | Device deployment, validation data, weather back-tests |
| Secondary | Maharashtra | Same KG and models; validate separately before making claims there |

The AICRP zone mapping differs by crop, which matters when importing trial data:

| Crop | Madhya Pradesh (Malwa) | Maharashtra |
|---|---|---|
| Wheat | Central Zone (CZ) | **Peninsular Zone (PZ)**, so different trials and varieties |
| Chickpea | Central Zone | Central Zone (verify) |
| Soybean | Central Zone (verify in AICRP Soybean reports) | verify (split between zones) |

Local institutions that breed or recommend varieties for Malwa, and are the first sources for varieties and trial data:
- **ICAR-IISR Indore** (soybean)
- **ICAR-IARI Regional Station Indore** (wheat, "HI" varieties)
- **RVSKVV Gwalior** and **JNKVV Jabalpur** (the MP state agricultural universities; JS/RVS soybean, JG/RVG chickpea)
- **ICAR-IIWBR Karnal** and **ICAR-IIPR Kanpur** (national AICRP coordination)

Season calendar for Malwa (typical; confirm per year):
- **Soybean** (kharif): sown with monsoon onset (late June–early July), harvested Sept–Oct.
- **Wheat and chickpea** (rabi): sown Oct–Nov, harvested Feb–Apr. Late-sown crops face terminal heat.

## Still open (decide before Phase 3)

- [ ] **Varieties:** notified varieties recommended for MP/Malwa (primary) and Maharashtra (target counts in
      RESEARCH_ROADMAP.md §10).
- [x] **Chickpea GDD base temperature:** decided (growth_stages.yaml). Soltani et al. (2006) model as primary,
      base-5 GDD for reporting, local recalibration later.
- [ ] **Out of scope for v1** (recorded so they aren't lost): wheat spot blotch, Karnal bunt, wheat blast;
      soybean yellow mosaic (MYMIV), Rhizoctonia aerial blight, Phytophthora root rot;
      chickpea Ascochyta blight, Botrytis grey mould.
