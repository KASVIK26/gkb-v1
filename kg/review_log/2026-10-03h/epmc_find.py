"""Find open-access papers for a topic and report which ones have gene/QTL tables or sentences. Usage: python batches/epmc_find.py "<europe pmc query>" [n]"""
import json, re, sys, urllib.parse, urllib.request
import curator.model  # noqa
from curator.graph.quote_audit import fetch_source_text

q, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 15
u = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urllib.parse.urlencode({"query": q + " AND OPEN_ACCESS:y", "format": "json", "pageSize": n, "resultType": "lite"})
for r in json.load(urllib.request.urlopen(u, timeout=40))["resultList"]["result"]:
    print(r.get("pmid"), r.get("pubYear"), "cited", r.get("citedByCount"), "|", re.sub("<[^>]+>", "", r["title"])[:110])
