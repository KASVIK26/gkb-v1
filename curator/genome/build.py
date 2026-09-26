"""Build data/interim/refgenes_<crop>.parquet for all 3 crops from the real genome files in
data/raw/ (RESEARCH_ROADMAP.md Phase 4 task 4.1/4.6). Callable from the CLI (`agrihub genome
build-refgenes`) or directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from curator.genome.refgenes import parse_ncbi_assembly_report, stream_ref_genes

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT_DIR / "data" / "raw"
DATA_INTERIM = ROOT_DIR / "data" / "interim"

# One entry per crop: the real files present in data/raw/ as of 2026-09-26.
CROP_SOURCES: dict[str, dict[str, Any]] = {
    "chickpea": {
        "gff": DATA_RAW / "cicar.ICC4958.gnm2.ann1.LCVX.gene_models_main.gff3",
        "assembly": "ICC4958.gnm2",
        "assembly_report": None,  # seqnames (e.g. cicar.ICC4958.gnm2.Ca1) are already readable
    },
    "soybean": {
        "gff": DATA_RAW / "glyma.Wm82.gnm6.ann1.PKSW.gene_models_main.gff3",
        "assembly": "Wm82.gnm6",
        "assembly_report": None,  # seqnames (e.g. glyma.Wm82.gnm6.Gm01) are already readable
    },
    "wheat": {
        "gff": DATA_RAW / "GCF_018294505.1_IWGSC_CS_RefSeq_v2.1_genomic.gff",
        "assembly": "IWGSC_CS_RefSeq_v2.1",
        "assembly_report": DATA_RAW / "GCF_018294505.1_IWGSC_CS_RefSeq_v2.1_assembly_report.txt",
    },
}


def build_crop(crop: str, *, out_dir: Path = DATA_INTERIM) -> pd.DataFrame:
    source = CROP_SOURCES[crop]
    chromosome_map = parse_ncbi_assembly_report(source["assembly_report"]) if source["assembly_report"] else None

    records = [
        {
            "locus_id": g.locus_id,
            "crop": g.crop,
            "assembly": g.assembly,
            "chromosome": g.chromosome,
            "start_bp": g.start_bp,
            "end_bp": g.end_bp,
            "strand": g.strand,
            "description": g.description,
            "domains": list(g.domains),
            "is_nlr": g.is_nlr,
            "nlr_class": g.nlr_class,
        }
        for g in stream_ref_genes(source["gff"], crop=crop, assembly=source["assembly"], chromosome_map=chromosome_map)
    ]
    df = pd.DataFrame.from_records(records)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"refgenes_{crop}.parquet"
    df.to_parquet(out_path, index=False)
    return df


def build_all(*, out_dir: Path = DATA_INTERIM) -> dict[str, pd.DataFrame]:
    return {crop: build_crop(crop, out_dir=out_dir) for crop in CROP_SOURCES}


def summarize(frames: dict[str, pd.DataFrame]) -> str:
    lines = []
    for crop, df in frames.items():
        nlr = df[df["is_nlr"]]
        lines.append(f"\n{crop}: {len(df):,} genes total, {len(nlr):,} NLR/RLK-flagged ({len(nlr) / len(df):.1%})")
        if len(nlr):
            by_class = nlr["nlr_class"].value_counts(dropna=False).sort_index()
            lines.append("  by class: " + ", ".join(f"{cls or 'unclassed'}={n}" for cls, n in by_class.items()))
            by_chrom = nlr["chromosome"].value_counts().sort_values(ascending=False).head(5)
            lines.append("  top chromosomes by NLR count: " + ", ".join(f"{c}={n}" for c, n in by_chrom.items()))
    return "\n".join(lines)
