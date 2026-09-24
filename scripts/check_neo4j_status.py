#!/usr/bin/env python3
"""
AgriHub-KB — Neo4j AuraDB live status check.

Run from the project root:
    python scripts/check_neo4j_status.py

Reads credentials from .env (or environment variables).
Uses the HTTPS Query API — no neo4j driver SDK required.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


# ── Load .env ────────────────────────────────────────────────────────────────
def _load_env(env_path: Path | None = None) -> None:
    path = env_path or (Path(__file__).resolve().parents[1] / ".env")
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


# ── Build HTTPS Query API URL ────────────────────────────────────────────────
def _query_url() -> str:
    import re
    uri = URI.rstrip("/")
    if uri.endswith("/query/v2"):
        return uri
    if re.match(r"^(neo4j|bolt)(\+s)?://", uri, re.I):
        from urllib.parse import urlparse
        host = urlparse(uri).hostname
        db   = DATABASE or (re.match(r"^([^.]+)\.", host or "").group(1) if host else "neo4j")
        return f"https://{host}/db/{db}/query/v2"
    if re.match(r"^https?://", uri, re.I):
        db = DATABASE or "neo4j"
        return f"{uri.rstrip('/')}/db/{db}/query/v2"
    raise SystemExit(f"Cannot parse NEO4J_URI: {URI!r}")


# ── Run Cypher ───────────────────────────────────────────────────────────────
_AUTH   = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
_URL    = None   # set after args parsed


def cypher(statement: str, params: dict | None = None) -> dict:
    payload = json.dumps({"statement": statement, "parameters": params or {}}).encode()
    req = urllib.request.Request(
        _URL,
        data=payload,
        headers={
            "Authorization": f"Basic {_AUTH}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        return {"_error": f"HTTP {exc.code}: {body[:400]}"}
    except Exception as exc:
        return {"_error": str(exc)}


def _vals(result: dict) -> list:
    return result.get("data", {}).get("values") or []


def _scalar(result: dict) -> int | str | None:
    rows = _vals(result)
    return rows[0][0] if rows else None


# ── Pretty helpers ───────────────────────────────────────────────────────────
W = 56

def section(title: str) -> None:
    print(f"\n  {'─' * (W-4)}")
    print(f"  {title}")
    print(f"  {'─' * (W-4)}")


def row(label: str, value, *, bar: bool = False) -> None:
    val_str = str(value) if value is not None else "—"
    suffix  = " " + ("█" * min(int(value or 0), 30)) if bar and isinstance(value, int) else ""
    print(f"  {label:<26} {val_str:>6}{suffix}")


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    global _URL

    if not URI or not USER or not PASSWORD:
        print("ERROR: NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD not set.")
        print("       Create a .env file in the project root (see .env.example).")
        return 1

    try:
        _URL = _query_url()
    except SystemExit as exc:
        print(exc); return 1

    print("=" * W)
    print("  AgriHub-KB  |  Neo4j AuraDB Status Check")
    print("=" * W)
    print(f"  Endpoint : {_URL}")
    print(f"  User     : {USER}")

    # ── Connection ping ──────────────────────────────────────────────────────
    ping = cypher("RETURN 'pong' AS ok")
    if "_error" in ping:
        print(f"\n  ❌  Connection FAILED\n  {ping['_error']}")
        return 1
    print("\n  ✅  Connected successfully")

    # ── Node counts ──────────────────────────────────────────────────────────
    section("Node counts")
    for label, q in [
        ("Crop",      "MATCH (n:Crop)      RETURN count(n)"),
        ("Variety",   "MATCH (n:Variety)   RETURN count(n)"),
        ("Gene",      "MATCH (n:Gene)      RETURN count(n)"),
        ("Disease",   "MATCH (n:Disease)   RETURN count(n)"),
        ("Treatment", "MATCH (n:Treatment) RETURN count(n)"),
    ]:
        row(label, _scalar(cypher(q)), bar=True)

    # ── Relationship counts ──────────────────────────────────────────────────
    section("Relationship counts")
    for label, q in [
        ("BELONGS_TO",          "MATCH ()-[r:BELONGS_TO]->()          RETURN count(r)"),
        ("CARRIES",             "MATCH ()-[r:CARRIES]->()             RETURN count(r)"),
        ("CONFERS_RESISTANCE_TO","MATCH ()-[r:CONFERS_RESISTANCE_TO]->() RETURN count(r)"),
        ("TREATED_BY",          "MATCH ()-[r:TREATED_BY]->()          RETURN count(r)"),
    ]:
        row(label, _scalar(cypher(q)), bar=True)

    # ── Graph contents ───────────────────────────────────────────────────────
    section("Graph contents")

    crops_r = cypher("MATCH (c:Crop) RETURN c.name ORDER BY c.name")
    crops   = [r[0] for r in _vals(crops_r)]
    print(f"  Crops     : {', '.join(crops) if crops else '(none yet)'}")

    dis_r    = cypher("MATCH (d:Disease) RETURN d.name ORDER BY d.name")
    diseases = [r[0] for r in _vals(dis_r)]
    print(f"  Diseases  : {', '.join(diseases) if diseases else '(none yet)'}")

    var_r    = cypher("MATCH (v:Variety) RETURN v.name, v.crop ORDER BY v.crop, v.name LIMIT 10")
    varieties = [f"{r[0]} ({r[1]})" for r in _vals(var_r)]
    if varieties:
        print(f"  Varieties : {', '.join(varieties)}" + (" …" if len(varieties) == 10 else ""))
    else:
        print("  Varieties : (none yet)")

    # ── Sample resistance edges ──────────────────────────────────────────────
    section("Sample resistance edges  (up to 8)")
    edges_r = cypher("""
        MATCH (g:Gene)-[r:CONFERS_RESISTANCE_TO]->(d:Disease)
        RETURN g.id, d.name, r.confidence, r.source
        LIMIT 8
    """)
    edges = _vals(edges_r)
    if edges:
        for gene, disease, conf, src in edges:
            conf_tag = {"Very High": "★★★", "High": "★★ ", "Medium": "★  "}.get(conf, "?  ")
            print(f"  {conf_tag}  {gene:<14} → {disease:<22}  ({src})")
    else:
        print("  (no resistance edges yet)")
        print("  Run: python curator/seed_loader.py   to load seed data")
        print("  Then: python curator/run_pipeline.py to process GFF3 files")

    # ── Constraints ──────────────────────────────────────────────────────────
    section("Schema constraints")
    const_r     = cypher("SHOW CONSTRAINTS YIELD name, type RETURN name, type")
    constraints = _vals(const_r)
    if constraints:
        for name, ctype in constraints:
            print(f"  ✓ {name}  [{ctype}]")
    else:
        print("  ⚠  No constraints — run init_constraints.py to create them")

    # ── AuraDB quota hint ────────────────────────────────────────────────────
    total_nodes = sum(
        _scalar(cypher(f"MATCH (n:{lbl}) RETURN count(n)")) or 0
        for lbl in ("Crop", "Variety", "Gene", "Disease", "Treatment")
    )
    total_rels = sum(
        _scalar(cypher(f"MATCH ()-[r:{rel}]->() RETURN count(r)")) or 0
        for rel in ("BELONGS_TO", "CARRIES", "CONFERS_RESISTANCE_TO", "TREATED_BY")
    )
    section("AuraDB Free-tier usage")
    row("Total nodes",          total_nodes, bar=False)
    row("Total relationships",  total_rels,  bar=False)
    row("Node limit",           50_000,      bar=False)
    row("Rel limit",            175_000,     bar=False)
    pct_n = f"{total_nodes/50_000*100:.1f}%"
    pct_r = f"{total_rels/175_000*100:.1f}%"
    print(f"  {'Capacity used':<26}  nodes {pct_n}  /  rels {pct_r}")

    print("\n" + "=" * W + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
