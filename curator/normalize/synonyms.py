"""Resolve free-text names (from papers, reports, users) to canonical entity IDs."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import yaml

from curator.model.enums import Crop
from curator.normalize.ids import lookup_key, parse_id

VOCAB_DIR = Path(__file__).resolve().parents[2] / "config" / "vocab"


class AmbiguousName(LookupError):
    """A name maps to more than one entity (e.g. 'rust' across three crops)."""

    def __init__(self, name: str, candidates: Iterable[str]):
        self.candidates = sorted(candidates)
        super().__init__(f"{name!r} is ambiguous: {', '.join(self.candidates)}")


class SynonymIndex:
    """name -> entity ID lookup, insensitive to case, spaces and punctuation.

    Ambiguity is reported, never guessed: resolve() raises AmbiguousName, and the
    caller must narrow by crop or send the item to human review.
    """

    def __init__(self) -> None:
        self._by_key: dict[str, set[str]] = defaultdict(set)

    def add(self, entity_id: str, *names: str) -> None:
        parse_id(entity_id)
        for name in names:
            key = lookup_key(name)
            if key:
                self._by_key[key].add(entity_id)

    def candidates(self, name: str, crop: Crop | str | None = None) -> set[str]:
        found = self._by_key.get(lookup_key(name), set())
        if crop is None:
            return set(found)
        crop = Crop(crop)
        return {eid for eid in found if parse_id(eid)[1] in (crop, None)}

    def resolve(self, name: str, crop: Crop | str | None = None) -> str | None:
        found = self.candidates(name, crop)
        if len(found) > 1:
            raise AmbiguousName(name, found)
        return next(iter(found), None)

    def __len__(self) -> int:
        return len(self._by_key)

    @classmethod
    def from_disease_vocab(cls, path: Path = VOCAB_DIR / "diseases.yaml") -> SynonymIndex:
        """Index disease names, synonyms and IDs from config/vocab/diseases.yaml."""
        vocab = yaml.safe_load(path.read_text(encoding="utf-8"))
        index = cls()
        for disease in vocab["diseases"]:
            slug = disease["id"].rsplit(":", 1)[1]
            index.add(
                disease["id"],
                disease["name"],
                slug.replace("_", " "),
                *disease.get("synonyms", []),
            )
        return index
