"""Print the table blocks (runs of text with many ' | ' separators) of a paper, with the 300 characters before each. Usage: python batches/table_blocks.py PMID [max_chars_per_block]"""
import re
import sys

import curator.model  # noqa: F401
from curator.graph.quote_audit import fetch_source_text

pid = sys.argv[1]
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 2500
t = fetch_source_text("pmid:" + pid) or ""
# a block starts at the first ' | ' after a sentence end and runs while separators keep appearing
starts = []
for m in re.finditer(r" \| ", t):
    if not starts or m.start() - starts[-1][1] > 400:
        starts.append([m.start(), m.start()])
    else:
        starts[-1][1] = m.start()
for a, b in starts:
    if b - a < 120:
        continue
    cap_start = max(0, a - 320)
    print("-" * 90)
    print(t[cap_start:min(b + 80, a + limit)].replace("\n", " "))
