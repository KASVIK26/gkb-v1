"""Map the exact `resistance` free-text phrases in config/sources/notified_varieties.yaml to
(disease_id, Reaction, stage) claims.

Deliberately EXACT-STRING matching, not a regex/keyword parser: every distinct phrase in the
source file (50 of them, as of 2026-09-26) was read and classified by hand once, here, rather
than trusted to a generic pattern that might silently misfire on a phrase not yet seen. A phrase
that isn't in this map raises `UnmappedResistanceText` instead of being guessed at -- see
`variety_import.py`, which treats that as a hard failure, not a warning.

Rules applied when classifying (documented once, here, not per-entry):
  - "resistant" / "resistance to" (no qualifier)  -> Reaction.R
  - "highly resistant" / "high resistance"         -> Reaction.R  (Reaction has no tier above R)
  - "fairly resistant"                             -> Reaction.R  (weakest form of "resistant";
                                                       flagged in a comment, not silently equated
                                                       to "highly resistant")
  - "moderately resistant" / "mod. resistant" / "moderate resistance" -> Reaction.MR
  - "tolerant" / "tolerance to"                    -> Reaction.MR  (an approximation: tolerance
                                                       and resistance are different concepts --
                                                       tolerant plants can still get infected but
                                                       don't lose much yield -- there is no better
                                                       bucket in the Reaction enum, so this is
                                                       flagged here rather than pretended away)
  - "adult plant resistance"                       -> Reaction.R, stage=ADULT (the one case in
                                                       this data where stage is stated explicitly)

Terms explicitly NOT mapped to any disease (and why), so nothing gets silently misattributed:
  - Wheat: Karnal bunt, foot rot, loose smut -- real wheat diseases, just not in the 17-disease
    scope (docs/scope.md).
  - Soybean: "Yellow Mosaic Virus" / "YMV" / "Mungbean Yellow Mosaic Virus" -- a DIFFERENT,
    whitefly-transmitted virus (genus Begomovirus) from "Soybean mosaic virus" (SMV, aphid-
    transmitted potyvirus) which IS in scope as dis:soybean:mosaic_virus. Conflating the two
    would be exactly the kind of error this project exists to avoid. YMV is explicitly listed as
    out-of-scope-for-v1 in docs/scope.md.
  - Soybean: "Alternaria leaf spot", "target leaf spot" -- different pathogens from frogeye leaf
    spot (Cercospora sojina), not in scope.
  - Soybean: "collar rot" -- not one of the 8 in-scope soybean diseases (collar rot IS in scope
    for chickpea, a different pathogen/host).
  - Chickpea: bare "root rot" / "root rot complex" (unqualified) -- ambiguous between dry root
    rot and collar rot in the source phrasing; skipped rather than guessed. "dry root rot"
    (qualified) maps to dis:chickpea:dry_root_rot without ambiguity.
  - Chickpea: "stunt", "Botrytis grey mould" / "BGM", "Ascochyta blight" -- real chickpea
    diseases, not in the 17-disease scope.
  - Pests, not diseases, skipped everywhere: girdle beetle, semi-looper, stem fly, pod borer /
    Helicoverpa, pulse beetle, nematode.
  - Abiotic traits, not diseases, skipped everywhere: drought, terminal heat, lodging,
    shattering, grain/chapatti/pasta quality.
"""

from __future__ import annotations

from curator.model.enums import PlantStage, Reaction

# (disease_id, reaction, stage) per phrase. An empty list is a deliberate, reviewed skip
# (e.g. the phrase names no in-scope disease at all) -- distinct from "not yet reviewed".
ReactionSpec = tuple[str, Reaction, PlantStage]

WHEAT: dict[str, list[ReactionSpec]] = {
    "field resistance to brown and black rust": [
        ("dis:wheat:leaf_rust", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:wheat:stem_rust", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "high resistance to black rust, brown rust; tolerant to terminal heat": [
        ("dis:wheat:stem_rust", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:wheat:leaf_rust", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "resistance to brown and black rust": [
        ("dis:wheat:leaf_rust", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:wheat:stem_rust", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "highly resistant to brown rust and foot rot; tolerant to black rust": [
        ("dis:wheat:leaf_rust", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:wheat:stem_rust", Reaction.MR, PlantStage.UNSPECIFIED),
    ],
    "resistance to black rust, brown rust; tolerant to terminal heat": [
        ("dis:wheat:stem_rust", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:wheat:leaf_rust", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "resistance to brown rust and black rust": [
        ("dis:wheat:leaf_rust", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:wheat:stem_rust", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "resistance to brown rust and loose smut": [
        ("dis:wheat:leaf_rust", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "fairly resistant to all three rusts": [
        ("dis:wheat:stem_rust", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:wheat:leaf_rust", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:wheat:stripe_rust", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "tolerance to major diseases": [],  # too vague to name a disease -- deliberately empty
    "resistance to brown rust": [("dis:wheat:leaf_rust", Reaction.R, PlantStage.UNSPECIFIED)],
    "resistance to brown rust, black rust": [
        ("dis:wheat:leaf_rust", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:wheat:stem_rust", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "resistance to brown rust, black rust, Karnal bunt": [
        ("dis:wheat:leaf_rust", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:wheat:stem_rust", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "resistance to all three rusts": [
        ("dis:wheat:stem_rust", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:wheat:leaf_rust", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:wheat:stripe_rust", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "resistance to black and brown rust": [
        ("dis:wheat:stem_rust", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:wheat:leaf_rust", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "tolerance to brown and black rust": [
        ("dis:wheat:leaf_rust", Reaction.MR, PlantStage.UNSPECIFIED),
        ("dis:wheat:stem_rust", Reaction.MR, PlantStage.UNSPECIFIED),
    ],
    "adult plant resistance to brown and black rust": [
        ("dis:wheat:leaf_rust", Reaction.R, PlantStage.ADULT),
        ("dis:wheat:stem_rust", Reaction.R, PlantStage.ADULT),
    ],
    "resistance to brown and black rust; heat tolerant": [
        ("dis:wheat:leaf_rust", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:wheat:stem_rust", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "high resistance to stem and leaf rust": [
        ("dis:wheat:stem_rust", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:wheat:leaf_rust", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "resistance to stem and leaf rusts": [
        ("dis:wheat:stem_rust", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:wheat:leaf_rust", Reaction.R, PlantStage.UNSPECIFIED),
    ],
}

SOYBEAN: dict[str, list[ReactionSpec]] = {
    "tolerant to major leaf, pod and root diseases; tolerant to girdle beetle and semi-looper": [],
    "resistant to Yellow Mosaic Virus and charcoal rot": [
        ("dis:soybean:charcoal_rot", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "resistant to charcoal rot; tolerant to girdle beetle and stem fly": [
        ("dis:soybean:charcoal_rot", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "resistant to bacterial pustule, pod blight, collar rot; tolerant to girdle beetle and stem fly": [
        ("dis:soybean:bacterial_pustule", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:soybean:pod_stem_blight", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "resistant to Yellow Mosaic Virus": [],
    "moderately resistant to Alternaria leaf spot, bacterial pustule, target leaf spot": [
        ("dis:soybean:bacterial_pustule", Reaction.MR, PlantStage.UNSPECIFIED),
    ],
    "moderately resistant to Mungbean Yellow Mosaic Virus": [],
    "good performance for charcoal-rot resistance in a comparative screening (AUDPC 56.81, root-rot severity score 1.57)": [],
    "reported rust and pest resistant": [("dis:soybean:rust", Reaction.R, PlantStage.UNSPECIFIED)],
}

CHICKPEA: dict[str, list[ReactionSpec]] = {
    "moderately resistant to wilt": [("dis:chickpea:fusarium_wilt", Reaction.MR, PlantStage.UNSPECIFIED)],
    "moderately resistant to wilt and dry root rot": [
        ("dis:chickpea:fusarium_wilt", Reaction.MR, PlantStage.UNSPECIFIED),
        ("dis:chickpea:dry_root_rot", Reaction.MR, PlantStage.UNSPECIFIED),
    ],
    "moderately resistant to wilt, dry root rot and collar rot (per this official document)": [
        ("dis:chickpea:fusarium_wilt", Reaction.MR, PlantStage.UNSPECIFIED),
        ("dis:chickpea:dry_root_rot", Reaction.MR, PlantStage.UNSPECIFIED),
        ("dis:chickpea:collar_rot", Reaction.MR, PlantStage.UNSPECIFIED),
    ],
    "tolerant to wilt": [("dis:chickpea:fusarium_wilt", Reaction.MR, PlantStage.UNSPECIFIED)],
    "highly resistant to wilt, dry root rot and stunt": [
        ("dis:chickpea:fusarium_wilt", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:chickpea:dry_root_rot", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "moderately resistant to stunt": [],
    "moderately resistant to dry root rot, collar rot and stunt; moderately resistant to pod borer": [
        ("dis:chickpea:dry_root_rot", Reaction.MR, PlantStage.UNSPECIFIED),
        ("dis:chickpea:collar_rot", Reaction.MR, PlantStage.UNSPECIFIED),
    ],
    "resistant to collar rot, root rot; moderately resistant to wilt and dry root rot": [
        ("dis:chickpea:collar_rot", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:chickpea:fusarium_wilt", Reaction.MR, PlantStage.UNSPECIFIED),
        ("dis:chickpea:dry_root_rot", Reaction.MR, PlantStage.UNSPECIFIED),
    ],
    "resistant to wilt": [("dis:chickpea:fusarium_wilt", Reaction.R, PlantStage.UNSPECIFIED)],
    "resistant to wilt and root rot complex": [
        ("dis:chickpea:fusarium_wilt", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "resistant to wilt, root rot and collar rot": [
        ("dis:chickpea:fusarium_wilt", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:chickpea:collar_rot", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "resistant to Fusarium wilt; moderately resistant to dry root rot": [
        ("dis:chickpea:fusarium_wilt", Reaction.R, PlantStage.UNSPECIFIED),
        ("dis:chickpea:dry_root_rot", Reaction.MR, PlantStage.UNSPECIFIED),
    ],
    "moderately resistant to wilt, dry root rot": [
        ("dis:chickpea:fusarium_wilt", Reaction.MR, PlantStage.UNSPECIFIED),
        ("dis:chickpea:dry_root_rot", Reaction.MR, PlantStage.UNSPECIFIED),
    ],
    "resistant to Fusarium wilt; moderate resistance to root rot": [
        ("dis:chickpea:fusarium_wilt", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "resistant to Fusarium wilt": [("dis:chickpea:fusarium_wilt", Reaction.R, PlantStage.UNSPECIFIED)],
    "moderately resistant to Fusarium wilt and dry root rot": [
        ("dis:chickpea:fusarium_wilt", Reaction.MR, PlantStage.UNSPECIFIED),
        ("dis:chickpea:dry_root_rot", Reaction.MR, PlantStage.UNSPECIFIED),
    ],
    "resistant to wilt; tolerant to pod borer": [
        ("dis:chickpea:fusarium_wilt", Reaction.R, PlantStage.UNSPECIFIED),
    ],
    "tolerant to Fusarium wilt": [("dis:chickpea:fusarium_wilt", Reaction.MR, PlantStage.UNSPECIFIED)],
    "moderately resistant to Fusarium wilt, dry root rot and Botrytis grey mould": [
        ("dis:chickpea:fusarium_wilt", Reaction.MR, PlantStage.UNSPECIFIED),
        ("dis:chickpea:dry_root_rot", Reaction.MR, PlantStage.UNSPECIFIED),
    ],
    "tolerant to wilt and drought": [("dis:chickpea:fusarium_wilt", Reaction.MR, PlantStage.UNSPECIFIED)],
    "moderately resistant to wilt and stunt": [
        ("dis:chickpea:fusarium_wilt", Reaction.MR, PlantStage.UNSPECIFIED),
    ],
    "moderately resistant to Fusarium wilt": [
        ("dis:chickpea:fusarium_wilt", Reaction.MR, PlantStage.UNSPECIFIED),
    ],
    "wilt resistant": [("dis:chickpea:fusarium_wilt", Reaction.R, PlantStage.UNSPECIFIED)],
}

BY_CROP: dict[str, dict[str, list[ReactionSpec]]] = {"wheat": WHEAT, "soybean": SOYBEAN, "chickpea": CHICKPEA}


class UnmappedResistanceText(KeyError):
    """A `resistance` phrase in notified_varieties.yaml has no reviewed entry above.

    Raised instead of silently guessing. Add a reviewed entry to this file (with the same
    reasoning discipline as the rest of the file) before re-running the import.
    """


def reaction_claims_for(crop: str, resistance_text: str | None) -> list[ReactionSpec]:
    if not resistance_text:
        return []
    table = BY_CROP[crop]
    if resistance_text not in table:
        raise UnmappedResistanceText(f"{crop}: unreviewed resistance text {resistance_text!r}")
    return table[resistance_text]
