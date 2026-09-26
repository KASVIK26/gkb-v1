"""Canonical identifiers and chromosome validation.

ID grammar (see docs/interfaces.md §1):
    crop-scoped   <prefix>:<crop>:<local>      var:wheat:HD3086, gene:wheat:Lr34, dis:wheat:stripe_rust
    crop          crop:<crop>
    pathogen      path:<slug>                  path:puccinia_striiformis_f_sp_tritici
    pathotype     pt:<pathogen_slug>:<local>   pt:puccinia_striiformis_f_sp_tritici:46S119
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

from curator.model.enums import CROP_SCOPED, ID_PREFIX, Crop, EntityType

_PREFIX_TO_TYPE = {prefix: etype for etype, prefix in ID_PREFIX.items()}
_LOCAL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]*$")
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


class InvalidId(ValueError):
    """Raised when a string does not follow the KG ID grammar."""


def slugify(text: str) -> str:
    """'Puccinia striiformis f. sp. tritici' -> 'puccinia_striiformis_f_sp_tritici'."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def lookup_key(text: str) -> str:
    """Case-, space- and punctuation-insensitive key used only for synonym lookup.

    'HD 3086', 'hd-3086' and 'HD3086' share one key. Never use it as an ID: case is
    meaningful in gene nomenclature (soybean rhg1 is recessive, Rhg4 dominant).
    """
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[\s\-_./()]+", "", text)


def variety_local(name: str) -> str:
    """'JS 95-60' -> 'JS9560', 'Pusa Chickpea 20211' -> 'PUSACHICKPEA20211'."""
    local = re.sub(r"[^A-Za-z0-9]+", "", unicodedata.normalize("NFKC", name)).upper()
    if not local:
        raise InvalidId(f"variety name {name!r} has no alphanumeric characters")
    return local


def gene_local(symbol: str) -> str:
    """Remove spaces between prefix and number ('Lr 34' -> 'Lr34'); keep case as written."""
    local = re.sub(r"\s+", "", symbol.strip())
    if not _LOCAL_RE.match(local):
        raise InvalidId(f"gene symbol {symbol!r} contains unsupported characters")
    return local


def make_id(etype: EntityType, local: str, crop: Crop | str | None = None) -> str:
    prefix = ID_PREFIX[etype]
    if etype is EntityType.CROP:
        return f"crop:{Crop(local).value}"
    if etype in CROP_SCOPED:
        if crop is None:
            raise InvalidId(f"{etype.value} IDs need a crop")
        entity_id = f"{prefix}:{Crop(crop).value}:{local}"
    else:
        entity_id = f"{prefix}:{local}"
    parse_id(entity_id)  # validate
    return entity_id


def variety_id(crop: Crop | str, name: str) -> str:
    return make_id(EntityType.VARIETY, variety_local(name), crop)


def gene_id(crop: Crop | str, symbol: str) -> str:
    return make_id(EntityType.GENE, gene_local(symbol), crop)


def parse_id(entity_id: str) -> tuple[EntityType, Crop | None, str]:
    """Validate an entity ID and return (type, crop, local part)."""
    prefix, _, rest = entity_id.partition(":")
    etype = _PREFIX_TO_TYPE.get(prefix)
    if etype is None or not rest:
        raise InvalidId(f"unknown or empty ID {entity_id!r}")

    if etype is EntityType.CROP:
        try:
            return etype, Crop(rest), rest
        except ValueError as exc:
            raise InvalidId(f"unknown crop in {entity_id!r}") from exc

    if etype in CROP_SCOPED:
        crop_part, _, local = rest.partition(":")
        try:
            crop = Crop(crop_part)
        except ValueError as exc:
            raise InvalidId(f"{entity_id!r}: second segment must be a crop") from exc
        if not _LOCAL_RE.match(local):
            raise InvalidId(f"{entity_id!r}: invalid local part {local!r}")
        return etype, crop, local

    if etype is EntityType.PATHOGEN:
        if not _SLUG_RE.match(rest):
            raise InvalidId(f"{entity_id!r}: pathogen IDs must be lowercase slugs")
        return etype, None, rest

    # Pathotype: pt:<pathogen_slug>:<designation>
    pathogen_slug, _, designation = rest.partition(":")
    if not _SLUG_RE.match(pathogen_slug) or not _LOCAL_RE.match(designation):
        raise InvalidId(f"{entity_id!r}: expected pt:<pathogen_slug>:<designation>")
    return etype, None, rest


def content_hash(prefix: str, payload: Any) -> str:
    """Deterministic ID from canonical JSON (sorted keys, no None values)."""

    def _clean(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: _clean(v) for k, v in sorted(value.items()) if v is not None}
        if isinstance(value, (list, tuple)):
            return [_clean(v) for v in value]
        return value

    canonical = json.dumps(_clean(payload), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return f"{prefix}:{hashlib.sha1(canonical.encode('utf-8')).hexdigest()[:16]}"


# ─────────────────────────── chromosome validation ───────────────────────────
# Physical chromosome labels in the reference assemblies we use.
_CHROMOSOME_RE: dict[Crop, re.Pattern[str]] = {
    # 1A..7D with optional arm (1BL, 7DS); wheat has 21 chromosomes, none numbered 8+.
    Crop.WHEAT: re.compile(r"^[1-7][ABD](?:[SL])?$"),
    # Gm01..Gm20 (also accept 1..20)
    Crop.SOYBEAN: re.compile(r"^(?:Gm)?(?:0?[1-9]|1[0-9]|20)$"),
    # Ca1..Ca8 (also CaLG1..CaLG8 linkage-group notation)
    Crop.CHICKPEA: re.compile(r"^Ca(?:LG)?0?[1-8]$"),
}


def validate_chromosome(crop: Crop | str, chromosome: str) -> str:
    crop = Crop(crop)
    if not _CHROMOSOME_RE[crop].match(chromosome):
        raise ValueError(f"{chromosome!r} is not a valid {crop.value} chromosome label")
    return chromosome
