#!/usr/bin/env python3
"""
AgriHub-KB — Database cleanup utility.

Deletes Gene nodes that have NO CONFERS_RESISTANCE_TO edges — i.e., raw
genomic gene models that were bulk-loaded from GFF3 but carry no resistance
knowledge.  The 22 seed resistance genes (Sr33, Lr18, etc.) are preserved
because they all have resistance edges.

Run from the project root:
    python scripts/cleanup_db.py            # dry-run: shows what would be deleted
    python scripts/cleanup_db.py --execute  # actually deletes the nodes

AuraDB Free-tier cap: 50,000 nodes.  After cleanup the graph should be
well within limits (~64 nodes total from seed data).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _load_env() -> None:
    path = Path(__file__).resolve().parents[1] / ".env"
    if not path.exists():
        return
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()

URI      = os.environ.get("NEO4J_URI", "").strip()
USER     = os.environ.get("NEO4J_USER", "").strip()
PASSWORD = os.environ.get("NEO4J_PASSWORD", "").strip()
DATABASE = os.environ.get("NEO4J_DATABASE", "").strip()


def _query_url() -> str:
    import re
    uri = URI.rstrip("/")
    if re.match(r"^(neo4j|bolt)(\+s)?://", uri, re.I):
        from urllib.parse import urlparse
        host = urlparse(uri).hostname
        db   = DATABASE or re.match(r"^([^.]+)\.", host or "").group(1)
        return f"https://{host}/db/{db}/query/v2"
    raise SystemExit(f"Cannot parse NEO4J_URI: {URI!r}")


def cypher(url: str, auth: str, statement: str, params: dict | None = None) -> dict:
    payload = json.dumps({"statement": statement, "parameters": params or {}}).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Authorization": f"Basic {auth}",
                 "Content-Type": "application/json",
                 "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def scalar(result: dict):
    try:
        return result["data"]["values"][0][0]
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete orphan Gene nodes from Neo4j")
    parser.add_argument("--execute", action="store_true",
                        help="Actually delete nodes (default is dry-run only)")
    args = parser.parse_args()

    if not URI or not USER or not PASSWORD:
        print("ERROR: NEO4J credentials not set. Check your .env file.")
        return 1

    url  = _query_url()
    auth = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()

    print("=" * 58)
    print("  AgriHub-KB  |  Database Cleanup")
    print(f"  Mode: {'EXECUTE — nodes will be deleted' if args.execute else 'DRY-RUN — no changes made'}")
    print("=" * 58)

    # Count orphan genes (no resistance edges)
    count_q = """
    MATCH (g:Gene)
    WHERE NOT (g)-[:CONFERS_RESISTANCE_TO]->()
    RETURN count(g) AS orphans
    """
    total_q  = "MATCH (g:Gene) RETURN count(g)"
    linked_q = "MATCH (g:Gene)-[:CONFERS_RESISTANCE_TO]->() RETURN count(DISTINCT g)"

    orphans = scalar(cypher(url, auth, count_q))
    total   = scalar(cypher(url, auth, total_q))
    linked  = scalar(cypher(url, auth, linked_q))

    print(f"\n  Gene nodes total          : {total:,}")
    print(f"  With resistance edges     : {linked:,}  ← will be KEPT")
    print(f"  Without resistance edges  : {orphans:,}  ← will be {'DELETED' if args.execute else 'deleted (run --execute)'}")

    if orphans == 0:
        print("\n  ✅  Nothing to clean up — no orphan genes found.")
        return 0

    if not args.execute:
        print(f"\n  DRY-RUN complete.  Run with --execute to delete {orphans:,} nodes.")
        return 0

    # Delete in batches of 10,000 to avoid memory pressure on AuraDB Free
    print(f"\n  Deleting {orphans:,} orphan Gene nodes in batches ...")
    deleted_total = 0
    batch_size = 10_000
    while True:
        delete_q = """
        MATCH (g:Gene)
        WHERE NOT (g)-[:CONFERS_RESISTANCE_TO]->()
        WITH g LIMIT $batch
        DELETE g
        RETURN count(*) AS deleted
        """
        result   = cypher(url, auth, delete_q, {"batch": batch_size})
        deleted  = scalar(result) or 0
        deleted_total += deleted
        print(f"    ... deleted {deleted_total:,} so far")
        if deleted < batch_size:
            break

    remaining = scalar(cypher(url, auth, total_q))
    print(f"\n  ✅  Done.  Deleted {deleted_total:,} orphan Gene nodes.")
    print(f"  Gene nodes remaining: {remaining:,}  (all have resistance edges)")

    # Show updated totals
    for label, q in [
        ("Crop",      "MATCH (n:Crop) RETURN count(n)"),
        ("Variety",   "MATCH (n:Variety) RETURN count(n)"),
        ("Gene",      "MATCH (n:Gene) RETURN count(n)"),
        ("Disease",   "MATCH (n:Disease) RETURN count(n)"),
        ("Treatment", "MATCH (n:Treatment) RETURN count(n)"),
    ]:
        print(f"  {label:<12}: {scalar(cypher(url, auth, q)):,}")

    pct = (remaining + 22) / 50_000 * 100   # rough estimate
    print(f"\n  AuraDB quota: ~{pct:.1f}% used  (limit 50,000 nodes)")
    print("=" * 58)
    return 0


if __name__ == "__main__":
    sys.exit(main())
