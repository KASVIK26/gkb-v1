"""Deterministic reader for the rust-screening tables of the AICRP Wheat & Barley "Crop Protection" progress reports.

Why a parser and not a language model: these tables are plain rows of numbers in the PDF text, a model asked to
"read" them returned a table (and a caption) that the report does not contain (see PHASES.md item 43), and a parser
cannot invent a row. Every claim it makes is backed by the exact row text, so `agrihub kg verify-quotes` finds it.

A row looks like  `15 cg 1029 10mr 1.8 20ms 4.1 10mr 0.7 100s 70.0 ...`: a serial number, the entry, then one (HS, ACI) pair per
disease column -- HS = highest score over the hot-spot centres ("20ms" = 20 % severity, moderately susceptible), ACI = average
coefficient of infection. The report prints the pair in either order depending on the table (the header says "aci hs" over data
that read "hs aci"), so each token is classified by its shape: a decimal is the ACI, a token ending in a response letter is HS.

Only the response letter is used for the reaction (R, MR, MS, S), as the report gives it. Trace responses (TR, TMR, TMS, TS),
"0" and rows with missing values (ng, ni) are skipped rather than interpreted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from curator.graph.quote_audit import normalise

COLUMN_WORDS = {
    "stem rust": ("dis:wheat:stem_rust", None),
    "leaf rust (s)": ("dis:wheat:leaf_rust", "leaf rust (S) centres"),
    "leaf rust (n)": ("dis:wheat:leaf_rust", "leaf rust (N) centres"),
    "stripe rust": ("dis:wheat:stripe_rust", None),
    "yellow rust": ("dis:wheat:stripe_rust", None),
    "leaf rust": ("dis:wheat:leaf_rust", None),
}
_HEADER = re.compile(r"(?:s\. ?no\.|avt no\.) (?:entries|entry) ((?:stem rust|leaf rust \([sn]\)|leaf rust|stripe rust|yellow rust)(?: (?:stem rust|leaf rust \([sn]\)|leaf rust|stripe rust|yellow rust))*)")
_TITLE = re.compile(r"table \d+\.\d+[.:]? [^.]{15,260}?(\d{4}-\d{2})")
_PAGE_HEADER = re.compile(r"aicrp-w&b, progress report, crop protection, (?:vol\. iii, )?\d{4} page [ivxlc\d]+")
_ACI = re.compile(r"\d+\.\d")
_HS = re.compile(r"(\d{1,3})?(tmr|tms|tr|ts|mr|ms|r|s)|0")
_RESPONSE = {"r": "R", "mr": "MR", "ms": "MS", "s": "S"}
_FLAGS = re.compile(r"\((?:c|d|i|dic\.?)\)|[*#]|\bq\b")


@dataclass(frozen=True)
class RustRow:
    table_title: str
    season: str
    sno: str
    entry: str            # as printed, flags included
    entry_clean: str      # flags removed
    values: tuple         # per column: (disease_id, location_label, hs_token, aci_token)
    row_text: str         # the exact normalised text of the row
    header_text: str      # the exact normalised header it was read under


def _pair(a: str, b: str):
    """(hs, aci) from two adjacent tokens in either order, else None. A trailing * or # (a footnote mark) is ignored."""
    a, b = a.rstrip("*#"), b.rstrip("*#")
    if _ACI.fullmatch(a) and _HS.fullmatch(b):
        return b, a
    if _HS.fullmatch(a) and _ACI.fullmatch(b):
        return a, b
    return None


def _skip_page_furniture(tokens: list[str], i: int, header_tokens: list[str]) -> int:
    """Skip the running page header and a repeated column header between two rows."""
    while i < len(tokens):
        window = " ".join(tokens[i:i + 12])
        m = _PAGE_HEADER.match(window)
        if m:
            i += len(m.group(0).split())
            continue
        if tokens[i:i + 3] == ["s.", "no.", "entries"] or tokens[i:i + 3] == ["s.", "no.", "entry"]:
            j = i
            while j < len(tokens) and tokens[j] not in ("1", "2") and not re.fullmatch(r"\d+[a-z]?", tokens[j]):
                j += 1
            i = j
            continue
        break
    return i


def parse_tables(raw_text: str) -> list[RustRow]:
    text = normalise(raw_text)
    rows: list[RustRow] = []
    for header in _HEADER.finditer(text):
        columns = re.findall(r"stem rust|leaf rust \([sn]\)|leaf rust|stripe rust|yellow rust", header.group(1))
        before = text[max(0, header.start() - 400): header.start()]
        title_match = list(_TITLE.finditer(before))
        title = title_match[-1].group(0) if title_match else ""
        season = title_match[-1].group(1) if title_match else ""
        # skip the per-column "aci hs" sub-header, then read rows
        if not season:
            continue
        tail = text[header.end(): header.end() + 60000]
        tokens = tail.split()
        i = 0
        while i < len(tokens) and i < 80 and tokens[i] != "1":
            i += 1  # the "aci hs aci hs ... av hs" sub-header (and any other column labels) up to serial number 1
        if i >= len(tokens) or tokens[i] != "1":
            continue  # a header repeated on a continuation page: the table was read from its first page
        header_tokens = []
        expected = 1
        while i < len(tokens):
            i = _skip_page_furniture(tokens, i, header_tokens)
            if i >= len(tokens) or not re.fullmatch(rf"{expected}", tokens[i]):
                # an infector/check line such as "20a infector ..." belongs between numbered rows: skip it
                m = re.fullmatch(rf"{expected - 1}[a-z]", tokens[i]) if i < len(tokens) and expected > 1 else None
                if not m:
                    break
                j = i + 1
                while j < len(tokens) and not re.fullmatch(rf"{expected}", tokens[j]):
                    j += 1
                i = j
                continue
            start = i
            need = len(columns) * 2
            k = i + 1
            parsed = None
            while k < len(tokens) and k - i <= 9:
                pairs = []
                ok = True
                for c in range(len(columns)):
                    pr = _pair(tokens[k + 2 * c], tokens[k + 2 * c + 1]) if k + 2 * c + 1 < len(tokens) else None
                    if pr is None:
                        ok = False
                        break
                    pairs.append(pr)
                if ok:
                    parsed = (k, pairs)
                    break
                k += 1
            if parsed is None:
                expected += 1
                # unreadable row (missing value like ng/ni): move on to the next serial number
                j = i + 1
                while j < len(tokens) and not re.fullmatch(rf"{expected}", tokens[j]):
                    j += 1
                i = j
                continue
            k, pairs = parsed
            entry = " ".join(tokens[i + 1:k])
            end = k + need
            row_text = " ".join(tokens[start:end])
            values = tuple((COLUMN_WORDS[col][0], COLUMN_WORDS[col][1], hs, aci) for col, (hs, aci) in zip(columns, pairs))
            rows.append(RustRow(title, season, tokens[i], entry, _clean(entry), values, row_text, header.group(0)))
            i = end
            while i < len(tokens) and not re.fullmatch(rf"{expected + 1}|{expected}[a-z]", tokens[i]):
                i += 1  # trailing columns of other diseases
            expected += 1
    return rows


def _clean(entry: str) -> str:
    return re.sub(r"\s+", " ", _FLAGS.sub(" ", entry)).strip()


def reaction_of(hs_token: str) -> str | None:
    """R / MR / MS / S from the response letter of an HS token, None for trace, zero or anything else."""
    m = re.fullmatch(r"(\d{1,3})?(tmr|tms|tr|ts|mr|ms|r|s)", hs_token)
    if not m or m.group(2) not in _RESPONSE:
        return None
    return _RESPONSE[m.group(2)]


# ───────────────────────────── from rows to a reviewable batch ─────────────────────────────
SCALE = "highest score (HS) over the hot-spot centres; response letter as reported (R/MR/MS/S)"


def claim_specs(rows: list[RustRow], *, source_id: str, entities: list) -> tuple[list[dict], list[str]]:
    """Curated-YAML claim specs for the rows that name a variety the KB already has; plus the entry names it did not know.

    Evidence is `field_multi_env` (the report is the trial's own record from several hot-spot centres) and the extractor is
    `parser:aicrp_rust@1`, so nothing here is model-made. The quote is the table title, its column header and the row, as three
    fragments of the report's own text.
    """
    from curator.extract.normalize import resolve_entity_from_bundle
    from curator.model import Claim
    from curator.model.enums import EntityType
    from curator.normalize.synonyms import AmbiguousName

    specs: dict[str, dict] = {}
    unknown: list[str] = []
    for row in rows:
        try:
            variety = resolve_entity_from_bundle(row.entry_clean, EntityType.VARIETY, entities, "wheat")
        except AmbiguousName:
            variety = None
        if variety is None:
            unknown.append(row.entry_clean)
            continue
        quote = f"{row.table_title} ... {row.header_text} ... {row.row_text}"
        for disease_id, location, hs, aci in row.values:
            reaction = reaction_of(hs)
            if reaction is None:
                continue  # trace / zero / unreadable: not interpreted
            qualifiers = {"reaction": reaction, "stage": "adult", "season": row.season, "score_raw": f"{hs.upper()} (ACI {aci})", "scale": SCALE}
            if location:
                qualifiers["location"] = location
            claim = Claim(type="VARIETY_REACTION", subject_id=variety, object_id=disease_id, qualifiers=qualifiers)
            spec = specs.setdefault(claim.id, {"type": "VARIETY_REACTION", "subject": variety, "object": disease_id,
                                               "qualifiers": dict(claim.qualifiers), "evidence": []})
            table_ref = (re.match(r"table \d+\.\d+", row.table_title) or re.match(r"", "")).group(0) or "table"
            zone = {"leaf rust (S) centres": "-S", "leaf rust (N) centres": "-N"}.get(location or "", "")
            slug = source_id.split(":", 1)[1]
            spec["evidence"].append({
                "source": source_id, "method": "field_multi_env", "locator": f"{table_ref}, row {row.sno}", "quote": quote,
                "extractor": "parser:aicrp_rust@1",
                "candidate_id": f"{slug}:{table_ref.replace('table ', 't')}:r{row.sno}:{disease_id.rsplit(':', 1)[1]}{zone}",
            })
    return list(specs.values()), sorted(set(unknown))
