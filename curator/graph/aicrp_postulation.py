"""Deterministic reader for the rust-gene postulation tables of the AICRP Wheat & Barley "Crop Protection" progress reports.

Each report prints, for the advanced varietal trial (AVT) entries, which Sr, Lr and Yr genes the Regional Station at Flowerdale (Shimla) postulated
from seedling tests with differential pathotypes (and, for some Yr genes, from linkage to an Lr or Sr gene), as three tables
"Sr genes / Lr genes / Yr genes in AVT entries during 2022-23". A row is one gene combination and the entries that carry it:

    lr23+10+ 7 dbw173*, hpw349, mp3556, nidw1149, pbw893, uas3022, wh1306

("lr23+10+" = Lr23 and Lr10, both postulated; 7 = how many entries follow). The report also gives the number of entries in each row, so the
reader checks that the names it finds are exactly that many and skips a row where they are not (a name split across lines, a missing comma)
rather than guessing. A name is trimmed of the report's flags -- (c) check variety, (d)/(i) trial group -- and kept only if the KB already has that
variety (the same policy as the rust-reaction reader); an AVT line that is not a released variety is not a Variety.

A name marked * ("different seed lot to that of previous cropping season") is NOT used: the report itself says the seed is not the one tested the year
before, and the two years' postulations for such an entry disagree (HD 3090: Sr31+Lr26+Yr9 in 2021-22, Lr13+Lr10+Yr2 in 2022-23), so which one
describes the variety is unknown.

No language model is involved, so the claims keep full weight; the postulation itself is an inference (seedling tests, linkage), which is why the
claim's method is `postulation` and the evidence method `postulation_pedigree`, not a marker result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from curator.graph.aicrp_rust import _PAGE_HEADER
from curator.graph.quote_audit import normalise

_CAPTION = re.compile(r"table (\d+\.\d+)[.:]? (sr|lr|yr)[- ]genes? in avt ?(?:entries|lines) during (\d{4}-\d{2})")
_COMBO = re.compile(r"(?<![a-z0-9+])((?:sr|lr|yr)(?:\d+[a-z]?|[a-z](?![a-z0-9]))(?:\+(?:\d+[a-z]?|[a-z](?![a-z0-9])))*\+)\s+(\d{1,3})(?=\s)")
_TOTAL = re.compile(r"\btotal (\d+)\b")
_NAME = re.compile(r"[a-z]{1,8} ?\d{1,5}[a-z]?(?: ?\((?:c|d|i)\))*(?: ?\*)?")
_FLAGS = re.compile(r"\s?\((?:c|d|i)\)|\s?\*")
_BREAK = "\x00"                       # where the running page header was cut out of a row
CLASS_NAME = {"sr": "Sr", "lr": "Lr", "yr": "Yr"}


@dataclass(frozen=True)
class PostulationRow:
    table: str                        # "table 2.9"
    season: str                       # "2022-23"
    gene_class: str                   # "yr"
    combo: str                        # "yr9+a+"
    genes: tuple                      # ("Yr9", "Yra")
    count: int                        # the number the report prints for the row
    entries: tuple                    # names as printed, flags removed
    count_ok: bool                    # len(entries) == count
    seed_lot_changed: tuple = ()      # entries the report marks * (different seed lot from the previous season): not used for claims
    header: str = ""                  # caption and column header, exactly as normalised
    row_fragments: tuple = ()         # the row's text; more than one when a page header fell inside it
    table_total: int | None = None    # the "total N" the table prints

    @property
    def quote(self) -> str:
        return " ... ".join((self.header, *self.row_fragments))


def gene_symbols(combo: str) -> tuple:
    """'sr8a+5+11+2+' -> ('Sr8a', 'Sr5', 'Sr11', 'Sr2'); 'yr9+a+' -> ('Yr9', 'Yra')."""
    parts = combo.rstrip("+").split("+")
    prefix = CLASS_NAME[parts[0][:2]]
    return tuple(prefix + (parts[0][2:] if i == 0 else p) for i, p in enumerate(parts))


def clean_name(name: str) -> str:
    return re.sub(r"\s+", " ", _FLAGS.sub("", name)).strip()


def parse_tables(raw_text: str) -> list[PostulationRow]:
    text = normalise(raw_text)
    rows: list[PostulationRow] = []
    for caption in _CAPTION.finditer(text):
        first = _COMBO.search(text, caption.end())
        if first is None or first.start() - caption.start() > 250:
            continue                  # a mention of the table in running text, not the table
        total = _TOTAL.search(text, first.start())
        if total is None:
            continue
        header = text[caption.start():first.start()].strip()
        region = _PAGE_HEADER.sub(_BREAK, text[first.start():total.start()])
        combos = list(_COMBO.finditer(region))
        for i, m in enumerate(combos):
            end = combos[i + 1].start() if i + 1 < len(combos) else len(region)
            names_text = region[m.end():end]
            fragments = [f.strip() for f in names_text.split(_BREAK)]
            found = [n.group(0) for f in fragments for n in _NAME.finditer(f)]
            entries = tuple(clean_name(n) for n in found)
            starred = tuple(clean_name(n) for n in found if n.rstrip().endswith("*"))
            first_fragment = f"{m.group(1)} {m.group(2)} {fragments[0]}".strip()
            row_fragments = (first_fragment, *[f for f in fragments[1:] if f])
            rows.append(PostulationRow(
                table=f"table {caption.group(1)}", season=caption.group(3), gene_class=caption.group(2), combo=m.group(1),
                genes=gene_symbols(m.group(1)), count=int(m.group(2)), entries=entries, count_ok=len(entries) == int(m.group(2)),
                seed_lot_changed=starred, header=header, row_fragments=tuple(row_fragments), table_total=int(total.group(1))))
    return rows


# ───────────────────────────── from rows to a reviewable batch ─────────────────────────────
EXTRACTOR = "parser:aicrp_postulation@1"


def claim_specs(rows: list[PostulationRow], *, source_id: str, entities: list) -> tuple[list[dict], list[dict], list[str], list[str]]:
    """(claim specs, new gene entities, entry names the KB does not have, rows skipped because the names did not add up to the printed count)."""
    from curator.extract.normalize import resolve_entity_from_bundle
    from curator.model import Claim
    from curator.model.enums import EntityType
    from curator.normalize.synonyms import AmbiguousName

    known_ids = {e.id for e in entities}
    new_genes: dict[str, dict] = {}
    specs: dict[str, dict] = {}
    unknown: set[str] = set()
    skipped: list[str] = []
    slug = source_id.split(":", 1)[1]

    def gene_id(symbol: str) -> str:
        found = resolve_entity_from_bundle(symbol, EntityType.GENE, entities + [], "wheat")
        if found:
            return found
        gid = f"gene:wheat:{symbol}"
        if gid not in known_ids and gid not in new_genes:
            new_genes[gid] = {"id": gid, "type": "Gene", "name": symbol, "crop": "wheat", "synonyms": [], "name_i18n": {}, "props": {"symbol": symbol}}
        return gid

    for row in rows:
        if not row.count_ok:
            skipped.append(f"{row.table} {row.combo} (printed {row.count}, found {len(row.entries)})")
            continue
        for name in dict.fromkeys(row.entries):
            if name in row.seed_lot_changed:
                continue
            try:
                variety = resolve_entity_from_bundle(name, EntityType.VARIETY, entities, "wheat")
            except AmbiguousName:
                variety = None
            if variety is None:
                unknown.add(name)
                continue
            for symbol in row.genes:
                gid = gene_id(symbol)
                claim = Claim(type="VARIETY_CARRIES_GENE", subject_id=variety, object_id=gid, qualifiers={"method": "postulation"})
                spec = specs.setdefault(claim.id, {"type": "VARIETY_CARRIES_GENE", "subject": variety, "object": gid,
                                                   "qualifiers": dict(claim.qualifiers), "evidence": []})
                ref = row.table.replace("table ", "t")
                spec["evidence"].append({
                    "source": source_id, "method": "postulation_pedigree", "locator": f"{row.table.capitalize()}, row {row.combo}",
                    "quote": row.quote, "extractor": EXTRACTOR,
                    "candidate_id": f"{slug}:{ref}:{row.combo}:{re.sub(r'[^a-z0-9]', '', name)}:{symbol}",
                })
    return list(specs.values()), list(new_genes.values()), sorted(unknown), skipped
