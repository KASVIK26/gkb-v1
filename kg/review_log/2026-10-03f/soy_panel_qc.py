"""QC and relatedness of the ICAR-IISR soybean GBS panel (icar_soybean_files/, never committed).
Reads the every-40th-SNP subsample of ImputedV6.GBS4Neeta.vcf.gz (Gmax_880_v6.0 coordinates; Beagle-imputed), maps SOY_nn ids to genotype names with the
two spreadsheets, and writes a sample table, a near-duplicate table and per-sample statistics next to the data (outside git)."""

import csv
import re
import sys

import numpy as np
import openpyxl

import os
S = "C:/Users/vikas/AppData/Local/Temp/claude/C--Users-vikas-gkb-v1/a204d952-4466-4fb7-8674-7c9cb736e0f6/scratchpad/"
OUT = "icar_soybean_files/derived/"
os.makedirs(OUT, exist_ok=True)

wb = openpyxl.load_workbook("icar_soybean_files/GWAS Sample with original Accession ID (1).xlsx", read_only=True, data_only=True)
name_of = {r[1]: str(r[2]).strip() for r in wb["Sheet2"].iter_rows(min_row=2, values_only=True) if r[1]}

samples, chroms, pos, af, dr2 = None, [], [], [], []
rows = []
with open(S + "imp_sample.tsv", encoding="utf-8") as fh:
    header = fh.readline().rstrip("\n").split("\t")
    samples = header[9:]
    for line in fh:
        f = line.rstrip("\n").split("\t")
        info = dict(kv.split("=") for kv in f[7].split(";") if "=" in kv)
        rows.append(np.fromiter((int(x[0]) + int(x[2]) for x in f[9:]), dtype=np.int8, count=len(samples)))
        chroms.append(f[0]); pos.append(int(f[1])); af.append(float(info.get("AF", "nan"))); dr2.append(float(info.get("DR2", "nan")))
G = np.vstack(rows)                       # SNPs x samples, alt allele count 0/1/2
af, dr2 = np.array(af), np.array(dr2)
print("subsampled SNPs", G.shape[0], "samples", G.shape[1], "chrom set", sorted(set(chroms))[:25])
keep = (af > 0.05) & (af < 0.95) & (dr2 > 0.8)
print("SNPs used (MAF>0.05, DR2>0.8):", int(keep.sum()))
idx = np.flatnonzero(keep)
if len(idx) > 40000:
    idx = np.sort(np.random.default_rng(1).choice(idx, 40000, replace=False))
X = G[idx].astype(np.float32)
het = (G == 1).mean(axis=0)
print("mean heterozygosity per sample: median %.3f max %.3f" % (np.median(het), het.max()))

# identity-by-state distance (fraction of allele dosage differences / 2) between all sample pairs
n = X.shape[1]
D = np.zeros((n, n), dtype=np.float32)
for i in range(n):
    D[i] = np.abs(X - X[:, [i]]).mean(axis=0) / 2
np.save(OUT + "ibs_distance.npy", D)

with open(OUT + "samples.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["sample", "genotype_name", "heterozygosity"])
    for s, h in zip(samples, het):
        w.writerow([s, name_of.get(s, ""), round(float(h), 4)])
pairs = []
for i in range(n):
    for j in range(i + 1, n):
        pairs.append((float(D[i, j]), samples[i], name_of.get(samples[i], ""), samples[j], name_of.get(samples[j], "")))
pairs.sort()
with open(OUT + "closest_pairs.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh); w.writerow(["ibs_distance", "sample_a", "name_a", "sample_b", "name_b"])
    for p in pairs[:600]:
        w.writerow([round(p[0], 5), *p[1:]])
print("closest pairs:")
for p in pairs[:25]:
    print("  %.4f %s (%s)  %s (%s)" % (p[0], p[1], p[2], p[3], p[4]))
