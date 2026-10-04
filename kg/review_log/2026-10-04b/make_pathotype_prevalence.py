"""State-wise pathotype distribution of wheat stripe rust and stem rust from the AICRP Crop Protection reports 2020-21, 2021-22 and 2022-23 (tables 8.13-8.16),
read by a parser: one PATHOTYPE_PREVALENCE claim per (pathotype, state, season) with the isolate counts as the evidence. A row is used only if its pathotype counts add up to the
number of isolates the report prints; frequency_pct is count / isolates analysed (a derived number, quoted row = the counts). The leaf-rust tables are not read: 2021-22 drops
its empty cells (columns cannot be aligned) and 2022-23's header is cut off one column short.
Output: kg/curated/pathotype_prevalence_v1.yaml."""

import re
from pathlib import Path

import yaml

import curator.model  # noqa: F401
from curator.cli import _build_bundle
from curator.graph.aicrp_rust import _PAGE_HEADER
from curator.graph.quote_audit import fetch_url_text, normalise

REPORTS = {
    "2020-21": ("aicrp_crop_protection_2020_21", "http://www.aicrpwheatbarleyicar.in/wp-content/uploads/2021/10/Crop-Protection-Report-2020-21-Compressed-1.pdf"),
    "2021-22": ("aicrp_crop_protection_2021_22", "https://www.aicrpwheatbarleyicar.in/wp-content/uploads/2022/08/Crop-Protection-Report-2021-22_Final-18.08.2022_compressed.pdf"),
    "2022-23": ("aicrp_crop_protection_2022_23", "https://www.aicrpwheatbarleyicar.in/wp-content/uploads/2023/08/Crop-Protection-Report2022-23_compressed.pdf"),
}
STATES = {"himachal pradesh": "HP", "punjab": "PB", "haryana": "HR", "uttarakhand": "UK", "rajasthan": "RJ", "uttar pradesh": "UP", "delhi": "DL", "gujarat": "GJ", "gujrat": "GJ",
          "maharashtra": "MH", "madhya pradesh": "MP", "tamil nadu": "TN", "karnataka": "KA", "chhattisgarh": "CG", "west bengal": "WB", "bihar": "BR"}
STATE_NAME = {"HP": "Himachal Pradesh", "PB": "Punjab", "HR": "Haryana", "UK": "Uttarakhand", "RJ": "Rajasthan", "UP": "Uttar Pradesh", "DL": "Delhi", "GJ": "Gujarat", "MH": "Maharashtra",
              "MP": "Madhya Pradesh", "TN": "Tamil Nadu", "KA": "Karnataka", "CG": "Chhattisgarh", "WB": "West Bengal", "BR": "Bihar"}
PATHOGEN = {"stripe": ("path:puccinia_striiformis_f_sp_tritici", "puccinia_striiformis_f_sp_tritici", "Pst"),
            "stem": ("path:puccinia_graminis_f_sp_tritici", "puccinia_graminis_f_sp_tritici", "Pgt")}
STRIPE_NAMES = r"238s119|110s119|46s119|110s84|47s103|46s103|79s68|78s84|6s0|7s0|0s0"
CAPTION = re.compile(r"table 8\.\d+[.:] pathotype distribution of (?:wheat )?(stripe|yellow|stem).{0,170}? during (\d{4}-\d{2})")


def clean(text: str) -> str:
    return _PAGE_HEADER.sub(" ", normalise(text))


def parse(text: str, season: str):
    for cap in CAPTION.finditer(text):
        kind = "stripe" if cap.group(1) in ("stripe", "yellow") else "stem"
        if cap.group(2) != season:
            continue
        body = text[cap.end():cap.end() + 2200]
        first = re.search(r"(?:^| )1\.? (?:himachal pradesh|gujarat|gujrat|madhya pradesh)", body)
        if not first:
            continue
        header = body[:first.start()].strip()
        if kind == "stripe":
            cols = re.findall(STRIPE_NAMES, re.sub(r"\s", "", header))
        else:
            tail = header[header.rindex("pathotype"):]
            tail = tail.split("¥", 1)[-1] if "¥" in tail else tail
            cols = re.findall(r"(?<![\w.])(\d{1,3}(?:-\d)?[a-z]?)(?![\w.])", tail)
        n = len(cols)
        rows_text = body[first.start():]
        end = re.search(r" total \d+", rows_text)
        rows_text = rows_text[:end.end() + 12 * n] if end else rows_text
        pat = re.compile(r"(?:(?<= )|^)(?:\d{1,2}\.? )?([a-z][a-z .&]+?) (\d{1,3}) ((?:(?:\d{1,3}|-) ){%d}(?:\d{1,3}|-))(?= (?:\d{1,2}\.? [a-z]|other|total|\*))" % (n - 1))
        for m in pat.finditer(rows_text):
            name = re.sub(r"\s+", " ", m.group(1)).strip()
            if name.startswith("other") or name == "total" or name not in STATES:
                continue
            total = int(m.group(2))
            counts = [0 if c == "-" else int(c) for c in m.group(3).split()]
            if sum(counts) != total:
                continue
            yield kind, cap.group(0), header, m.group(0).strip(), STATES[name], total, dict(zip(cols, counts))


def main():
    bundle = _build_bundle()
    known = {e.id for e in bundle.entities}
    entities, claims, seen_path = {}, {}, set()
    stats = []
    for season, (slug, url) in REPORTS.items():
        text = clean(fetch_url_text(url) or "")
        assert text, season
        n_rows = 0
        year = int(season[:2] + season[5:7]) if False else 2000 + int(season[5:7])
        for kind, caption, header, row, code, total, counts in parse(text, season):
            n_rows += 1
            path_id, path_slug, prefix = PATHOGEN[kind]
            zone_id = f"zone:wheat:{code}"
            if zone_id not in known and zone_id not in entities:
                entities[zone_id] = {"id": zone_id, "type": "AgroZone", "name": f"{code} (wheat)", "crop": "wheat", "synonyms": [STATE_NAME[code]], "name_i18n": {},
                                     "props": {"system": "state", "states": [code]}}
            for pt, cnt in counts.items():
                if not cnt:
                    continue
                local = pt.upper()
                pid = f"pt:{path_slug}:{local}"
                if pid not in known and pid not in entities:
                    entities[pid] = {"id": pid, "type": "Pathotype", "name": f"{prefix} {local}", "crop": "wheat", "synonyms": [local, f"{prefix}{local}"], "name_i18n": {},
                                     "props": {"designation": local}}
                key = (pid, zone_id, year)
                claims[key] = {"type": "PATHOTYPE_PREVALENCE", "subject": pid, "object": zone_id,
                               "qualifiers": {"years": [year], "frequency_pct": round(100 * cnt / total, 1)},
                               "evidence": [{"source": f"doc:{slug}", "method": "official_document", "locator": f"{caption.split(':')[0].capitalize()}, {code} row",
                                             "extractor": "parser:aicrp_pathotype@1", "quote": f"{caption} ... {header} ... {row}",
                                             "candidate_id": f"pathotype_prev:{slug}:{kind}:{code}:{local}"}]}
        stats.append((season, n_rows))
    header = ("State-wise pathotype distribution of wheat stripe rust and stem rust (AICRP Crop Protection reports 2020-21 to 2022-23, tables 8.13-8.16), read by\n"
              "batches/make_pathotype_prevalence.py (no model). Only rows whose pathotype counts add up to the printed number of isolates; frequency_pct = count / isolates analysed;\n"
              "`years` is the end year of the crop season. Leaf-rust tables are not read (empty cells or cut header). Reviewed 2026-10-04 (kg/review_log/2026-10-04a_pathotype_prevalence.md).")
    Path("kg/curated/pathotype_prevalence_v1.yaml").write_text("".join(f"# {l}\n" for l in header.splitlines()) + "\n" + yaml.safe_dump(
        {"sources": [], "entities": list(entities.values()), "claims": list(claims.values())}, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8", newline="\n")
    print("rows per season:", stats, "| claims", len(claims), "| new entities", len(entities))
    from collections import Counter
    print(Counter((k[1], k[2]) for k in claims).most_common(30))


if __name__ == "__main__":
    main()
