# Risk engine: design decisions (parked; very low priority as of 2026-10-03)

Priority order decided 2026-10-03: **resistance-gene knowledge first** (genes linked to varieties, every in-scope disease covered), then reactions/pathotype data,
and only then the engine. Nothing below is built. The dashboard's "Check sensor readings" tab stays what it is: a snapshot demo of the trigger library.

## Scope of the real engine (built here, hosted separately)
The engine is a library plus `POST /api/risk`. Delivery of flags to phones or the researcher dashboard (edge functions, triggers, push) is a separate part and
only consumes the engine's response.

## Capability-adaptive by design
The engine must say what it can say with whatever sensors a field has, and say plainly what it cannot:
- Each trigger condition names a variable (`config/vocab/sensors.yaml`: air temperature, RH, rain, soil moisture, soil temperature, NPK, light, and a leaf-wetness
  sensor when fitted). The prototype has no leaf-wetness sensor; the vocabulary's derived proxies (`rh_ge_90_h`, `est_leaf_wet_h`, `soil_wetting_event`) stand in
  until one is added. A real sensor, when present, takes precedence over its proxy.
- For each disease the engine evaluates the conditions it has data for and reports the rest as "cannot evaluate: needs <variable>". It never guesses a missing value.
- Output per disease: a risk level, the conditions matched / unmatched / not evaluable, the evidence tier behind each trigger, the variety's reaction and its tier,
  and the confidence of the whole result (it falls with every missing input). More sensor types give a finer analysis; a field with only soil moisture, or only NPK,
  still gets the analyses those readings support (for example soil-borne diseases from moisture and soil temperature; nutrient status as a susceptibility modifier only
  where a cited claim links it), and a list of what adding another sensor would unlock.
- Aggregation is real: each condition is computed over its own window (mean / sum / min / max over `window_h` hours) from a time series, gated by crop stage estimated
  from the sowing date; the snapshot form in the GKB demo is not a substitute.
- Output is an *unvalidated indicator* until back-tested (thresholds are untuned literature ranges).

## Inputs the KG must have first (why this waits)
Variety susceptibility (reactions are thin outside wheat), gene resistance linked to varieties and diseases, pathotype prevalence (0 claims today), crop-stage windows,
and severity ground truth for back-testing (older AICRP reports, read by the deterministic parsers).
