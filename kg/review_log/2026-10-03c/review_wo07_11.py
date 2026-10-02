"""Reviewer decisions for WO07-WO11 (2026-10-03; reviewer: Claude, for the project owner; a crop scientist reviews the live graph).
Input: batches/WO07.jsonl, WO08.jsonl, WO09.jsonl, WO11c.jsonl, WO11g.jsonl.  Output: batches/WO07.reviewed.jsonl ... WO11.reviewed.jsonl.
WO10 (epidemiology triggers) is not a claims file and is not converted (see the review log).
Every edit is a quote rebuilt from the source's own wording (and re-checked by the verifier), an alias made of words literally in the quote,
a qualifier that the quote does not state removed, or a drop."""

import copy
import json
import re


def load(name):
    return [json.loads(line) for line in open(f"batches/{name}.jsonl", encoding="utf-8")]


def save(name, rows):
    open(f"batches/{name}.reviewed.jsonl", "w", encoding="utf-8").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


# ───────────────────────────── WO07: IIWBR Mehtaensis newsletters (pathotypes) ─────────────────────────────
WO07_DROP = {
    "WO07-0003": "'the yellow rust pathogen POPULATION remained avirulent to Yr5, ...' says nothing about pathotype 238S119 specifically; the model attached a pathotype",
    "WO07-0004": "as WO07-0003", "WO07-0005": "as WO07-0003",
    "WO07-0007": "'the stem rust population was avirulent to Sr31 ...' is not about pathotype 11 specifically; as WO07-0003",
}
PATHOGEN_ALIAS = {   # the quote's own words for the pathogen
    "WO07-0001": "wheat yellow rust", "WO07-0002": "wheat yellow rust", "WO07-0006": "black rust",
    "WO07-0008": "brown rust", "WO07-0009": "brown rust", "WO07-0010": "brown rust",
    "WO07-0013": "Puccinia striiformis tritici", "WO07-0015": "P. graminis tritici",
}


def review_wo07():
    out = []
    for c in load("WO07"):
        cid = c["candidate_id"]
        if cid in WO07_DROP:
            continue
        if cid in PATHOGEN_ALIAS:
            c["object"]["alias_in_quote"] = PATHOGEN_ALIAS[cid]
        if cid == "WO07-0014":      # a page break (running header "Mehtaensis 40(2): July, 2020 Page 3") falls inside the sentence
            c["quote"] = "Pathotypes 77-9, 77-5 and 77-1 were the most predominant in ... triticina (Pt; brown rut) population and were identified in 50.3, 28.2 and 7.1 % of the samples, respectively."
            c["object"]["alias_in_quote"] = "triticina"
        m = re.fullmatch(r"Pst(\d+S\d+)", c["subject"]["text"])
        if m:                       # one pathotype, one name: the newsletters write 46S119, the genome paper Pst46S119
            c["subject"]["alias_in_quote"] = c["subject"]["text"]
            c["subject"]["text"] = m.group(1)
            c["object"]["alias_in_quote"] = "Pst"
        c["qualifiers"].pop("year", None)       # 2026 is the newsletter's year, not stated as the year of the observation
        out.append(c)
        if cid == "WO07-0011":      # the same sentence names Lr39 as defeated too
            extra = copy.deepcopy(c)
            extra["candidate_id"] = "WO07-0019"
            extra["subject"]["text"] = "Lr39"
            out.append(extra)
    save("WO07", out)
    return len(out)


# ───────────────────────────── WO08: PPQS / CIBRC fungicide recommendations ─────────────────────────────
WO08_DROP = {
    "WO08-0007": "AESA lists mancozeb 75% WP @ 6-8 kg in 300 l/acre: ten times the usual label dose (6-8 g/l would be 2 kg); a printing error in the source, not asserted",
    "WO08-0008": "as WO08-0007", "WO08-0009": "as WO08-0007",
    "WO08-0012": "the CIBRC row reads 'Stemrust (B.graminis f.sp. tritici)': a stem-rust label with the powdery-mildew pathogen's name; the source contradicts itself",
}
CIBRC_HEADER = "Crop Common name of the disease Dosage per ha Waiting period from last application to harvest (in days) a. i. (g) Formulation (g/ml)/% Dilution in water(L)"
AESA_PROP = "Black, brown and yellow rust ... Chemical control: • Propiconazole 25% EC @ 200 ml in 200 l of water/acre"
AESA_TEB = "Black, brown and yellow rust ... Chemical control: • Propiconazole 25% EC @ 200 ml in 200 l of water/acre or tebuconazole 25% EC @ 200 ml in 200 l of water/acre"
CIBRC_ROWS = {   # candidate -> (crop cell, disease row exactly as printed, waiting days, dilution)
    "WO08-0010": ("Wheat", "Stripe rust /Yellow Rust (P. striiformis) 125gm 500gm 750 30", 30, 750),
    "WO08-0011": ("Wheat", "Leaf rust / Brown Rust (Pucciniarecondite F.sp. tritici) 125gm 500gm 750 30", 30, 750),
    "WO08-0013": ("Soyabean", "Rust(Phakopsoa pachyrhizi) 125gm 500gm 500 26", 26, 500),
}


def review_wo08():
    out = []
    for c in load("WO08"):
        cid = c["candidate_id"]
        if cid in WO08_DROP:
            continue
        adv = c["object"]["advisory"]
        if cid in CIBRC_ROWS:
            crop, row, days, dil = CIBRC_ROWS[cid]
            c["quote"] = f"{CIBRC_HEADER} ... Propiconazole 25% EC ... {crop} ... {row}"
            adv["dose"] = f"125 g a.i. / 500 g formulation / {dil} L water per ha"
            adv["timing"] = f"waiting period from last application to harvest: {days} days"
        elif cid in ("WO08-0001", "WO08-0002", "WO08-0003"):
            c["quote"] = AESA_PROP
            adv.pop("timing", None)      # the model's "timing" was the section heading, not a timing
        elif cid in ("WO08-0004", "WO08-0005", "WO08-0006"):
            c["quote"] = AESA_TEB
            adv.pop("timing", None)
        else:
            adv.pop("timing", None)
        out.append(c)
    save("WO08", out)
    return len(out)


# ───────────────────────────── WO09: fungicide field trials ─────────────────────────────
WO09_DROP = {"WO09-0004": "tebuconazole 25.9% EC is the runner-up ('followed by') in the same sentence; kept only the best treatment"}


def review_wo09():
    out = []
    for c in load("WO09"):
        cid = c["candidate_id"]
        if cid in WO09_DROP:
            continue
        adv = c["object"]["advisory"]
        if cid in ("WO09-0001", "WO09-0002"):
            adv.pop("region", None)      # "ICAR-IISR, Indore" is where the recommendation came from, not stated as the trial site in the quoted text
        if cid == "WO09-0002":
            c["quote"] = ("other treatments were selected as picoxystrobin 22.52% w/w SC @ 0.08%, propiconazole 25% w/w EC @ 0.1%, pyraclostrobin 20% w/w WG @ 0.1%, "
                          "hexaconazole 5% EC @ 0.1% and control was untreated. ... foliar spray of each treatment was given thrice, each at 30 days after sowing (DAS), 45 DAS and 60 DAS. "
                          "... all the treatments were found significantly effective against soybean anthracnose during both the years.")
            c["subject"]["alias_in_quote"] = "soybean anthracnose"
            adv["dose"] = "0.1%"
            adv["timing"] = "three foliar sprays, at 30, 45 and 60 days after sowing"
        if cid == "WO09-0003":
            c["quote"] = ("for the management of stem rust of wheat at Indore location during 2022-2023. ... The foliar spray of Tebuconazole 50% + Trifloxystrobin 25% WG @ 0.06 % "
                          "followed by Tebuconazole 25.9 % EC @0.1% was found significantly best among all the treatments when applied at disease initiation and repeated after 14 days.")
            c["subject"]["alias_in_quote"] = "stem rust"
        if cid == "WO09-0005":
            c["quote"] = ("against the leaf rust of wheat, the study's finding showed that, of the different fungicides treatments, (T 3 ) Tebuconazole 50% + Trifloxystrobin 25% WG @ 0.1% "
                          "was the most successful, as evidenced by the significantly higher grain yield (29.11 q/ha), plant height (80.95 cm), 1000 grain weight (49.19 gm) and dry matter yield (54.11 q/ha)")
            c["subject"]["alias_in_quote"] = "leaf rust"
            adv.pop("region", None)      # "Mahabaleshwar / Pune" is not on the page
            adv.pop("timing", None)      # "fungicidal spray" is not a timing
        out.append(c)
    save("WO09", out)
    return len(out)


# ───────────────────────────── WO11: ChatGPT "complete" run (c) and Grok run (g) ─────────────────────────────
#  - WO11g-0004 (JS 20-20, charcoal rot, pmid 37264096): the paper calls it a 'genotype'; not shown to be a released variety
# Kept: released/KB-known cultivars, causal-organism statements, gene -> disease statements. Left out on purpose:
#  - germplasm accessions and breeding lines (IC/ICC/PI/EC/CAT/CIM numbers, NB 208, AGS 136 A, NRC 202, PG 06102 ...): not varieties a farmer can sow
#  - WO11-0009..0029 (bacterial pustule table, 21 rows): the paper (10.9734/ijpss/...) is not on Europe PMC and its page does not carry the table: unverifiable
#  - WO11-0031..0034 (marker -> rxp QTL): the quote does not name the marker
#  - WO11-0069 (Rhizoctonia bataticola): not in the pathogen vocabulary (Macrophomina phaseolina is the accepted name)
#  - WO11-0076..0078, 0081 (US lines PI 96983, L29, V94-5152, Davis carry Rsv/Rcs genes): not Indian varieties
#  - WO11-0030 (bacterial pustule -> Xanthomonas): verified at ingest, but the journal's site now answers HTTP 403, so the quote can no longer be re-audited
#  - WO11-0080 (Rcs3 -> frogeye): same paper and same statement as a claim already in the KB (no new source)
#  - WO11-0082..0085 (CIM lines): quote not in the source
#  - WO11-0070, 0072: unverifiable (publisher page lacks the quote)
C_KEEP = {1, 5, 8, 35, 36, 37, 38, 39, 42, 44, 50, 71, 73, 74, 75, 79}
ANTHRACNOSE_INTRO = "Anthracnose disease caused by Colletotrichum truncatum is a major disease in soybean in India."


def review_wo11():
    out = []
    for c in load("WO11c"):
        n = int(c["candidate_id"].split("-")[1])
        if n not in C_KEEP:
            continue
        c["candidate_id"] = f"WO11c-{n:04d}"
        if n in (1, 5):
            c["quote"] = f"{ANTHRACNOSE_INTRO} ... {c['quote']}"
            c["object"]["alias_in_quote"] = "Anthracnose disease"
            c["qualifiers"].pop("stage", None)      # "adult" is not in the quote
            c["qualifiers"]["stage"] = "unspecified"
        if n == 8:
            c["subject"]["alias_in_quote"] = "Anthracnose disease"
        if n in (73, 74, 75):
            c["object"]["alias_in_quote"] = "SMV"   # soybean mosaic virus (never YMV)
            c["qualifiers"].pop("spectrum", None)   # same gene -> disease claim already in the KB: without the qualifier this is a second source for it, not a duplicate edge
        out.append(c)

    for c in load("WO11g"):
        n = int(c["candidate_id"].split("-")[1])
        if n not in (1, 2):
            continue   # the rest give a title but no pmid/doi: nothing to verify against a registry
        c["candidate_id"] = f"WO11g-{n:04d}"
        adv = (c["object"].get("advisory") or {})
        if n == 1:
            c["subject"]["alias_in_quote"] = "rust severity"
            adv["timing"] = "two sprays at 15 days interval"
            adv.pop("region", None)      # Dharwad is not in the quoted sentence
        if n == 2:
            c["quote"] = ("A field experiment was conducted to evaluate different fungicides against chickpea rust caused by Uromyces ciceris-arietini at Main Agricultural Research Station (MARS), "
                          "Dharwad and ARS, Arabhavi during Rabi 2017 and 2018. ... " + c["quote"])
            c["subject"]["alias_in_quote"] = "chickpea rust"
            adv["region"] = "Dharwad and Arabhavi"
            adv.pop("timing", None)
        out.append(c)
    save("WO11", out)
    return len(out)


if __name__ == "__main__":
    print("WO07", review_wo07(), "| WO08", review_wo08(), "| WO09", review_wo09(), "| WO11", review_wo11())
