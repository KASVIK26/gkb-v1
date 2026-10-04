# Module interfaces (IoT ↔ API ↔ KG ↔ models)

⚠️ **Superseded: the read API, identifiers, feature vector and versioning are now in [INTEGRATION.md](INTEGRATION.md) (2026-10-04).** The text below is the 2026-09-25 draft; see also [PHASES.md](../PHASES.md). Sections 2–4 below (device registration, sensor
ingest, `/v1/risk`) assumed the IoT device stores its readings in this repo's database. It does not — the IoT
device has its own Supabase project. Sections 1 (identifiers), 5 (phenomic model) and 6 (hardware notes) still
hold. Not yet rewritten; pending the open questions in PHASES.md.

Status: draft v1, 2026-09-25. Machine-readable sources of truth:

| What | File |
|---|---|
| Disease IDs, pathogens, driver types | `config/vocab/diseases.yaml` |
| Sensor variables, units, QC, derived proxies | `config/vocab/sensors.yaml` |
| Growth stages (BBCH + display scales) | `config/vocab/growth_stages.yaml` |

`tests/test_vocab.py` checks that the three files stay consistent.

## 1. Identifiers

- Diseases: `dis:<crop>:<slug>` (e.g. `dis:wheat:stripe_rust`). The phenomic model's class labels **must** use these IDs.
- Varieties: `var:<crop>:<normalised_name>` (e.g. `var:wheat:HD3086`), defined in Phase 3.
- Growth stage: BBCH integer 0–99, or `SYS_PRE` / `SYS_POST`.
- Devices: `dev:<serial>`. Fields: `fld:<uuid>`.

## 2. Device registration (once per install)

```json
{
  "device_id": "dev:AGN-0001",
  "field_id": "fld:…",
  "location": {"lat": 22.72, "lon": 75.86, "elevation_m": 550},
  "install": {
    "sn3002":  {"depth_cm": 15, "soil_texture": "vertisol"},
    "aht20":   {"height_cm": 50, "radiation_shield": true},
    "bme280":  {"height_cm": 50, "radiation_shield": false},
    "veml7700":{"height_cm": 60, "orientation": "up"},
    "primary_air_sensor": "aht20"
  },
  "crop_season": {"crop": "soybean", "variety": "var:soybean:JS9560", "sowing_date": "2026-06-28"}
}
```

Install metadata is required. Soil readings at 5 cm and at 20 cm are not comparable, and the research dataset
must record which one it is.

## 3. Ingest: `POST /v1/ingest` (device key in `Authorization: Bearer`)

The device aggregates its 2-second samples into **1-minute records** and uploads a batch every 15 minutes.
While offline it buffers to flash and resends with the original timestamps. Timestamps are **UTC**. Ingest is
idempotent on `(device_id, ts)`.

```json
{
  "device_id": "dev:AGN-0001",
  "firmware": "1.4.2",
  "records": [
    {
      "ts": "2026-08-23T16:16:00Z",
      "soil_moisture_vwc": {"mean": 46.6, "min": 46.5, "max": 46.7, "n": 1},
      "soil_temp_c": {"mean": 27.2, "min": 27.2, "max": 27.2, "n": 1},
      "soil_ph": {"mean": 6.1, "n": 1},
      "soil_ec": {"mean": 267, "n": 1},
      "soil_n": {"mean": 12, "n": 1}, "soil_p": {"mean": 18, "n": 1}, "soil_k": {"mean": 43, "n": 1},
      "soil_salinity": {"mean": 146, "n": 1}, "soil_tds": {"mean": 133, "n": 1},
      "air_temp_c_aht20": {"mean": 29.41, "min": 29.38, "max": 29.45, "n": 6},
      "air_rh_aht20": {"mean": 81.18, "min": 81.0, "max": 81.3, "n": 6},
      "air_temp_c_bme280": {"mean": 29.29, "n": 6},
      "air_rh_bme280": {"mean": 71.87, "n": 6},
      "air_pressure_hpa": {"mean": 952.33, "n": 6},
      "light_lux": {"mean": 50.75, "min": 12.0, "max": 88.0, "n": 6}
    }
  ],
  "health": {"soil_reads_ok": 37, "soil_reads_failed": 0, "modbus_requests": 111, "rx_bytes": 1221,
             "time_source": "ntp", "rssi_dbm": -61}
}
```

Response: `{"accepted": n, "duplicates": n, "rejected": [{"ts": "...", "reason": "..."}]}`.

## 4. Risk: `POST /v1/risk`

The server builds the input from ingested data. The IoT app can also send a window explicitly (e.g. for testing).

```json
{
  "field_id": "fld:…",
  "at": "2026-08-23T18:00:00Z",
  "horizon_days": 3
}
```

```json
{
  "kg_release": "kg-2026.10.1",
  "crop": "soybean", "variety": "var:soybean:JS9560",
  "growth_stage": {"bbch": 65, "display": "R2", "source": "estimated_gdd", "confidence": 0.7},
  "flags": [
    {
      "disease": "dis:soybean:rust",
      "risk": 0.72, "level": "high",
      "why": {
        "conditions_met": ["rh_ge_90_h = 11 (≥ threshold)", "air_temp_c mean 23.4 in favourable range"],
        "variety_reaction": {"reaction": "MS", "tier": "B", "claim_ids": ["claim:…"]},
        "stage_in_window": true,
        "forecast": "rain_mm next 72 h = 38"
      },
      "advisory": {"text_en": "…", "text_hi": "…", "source": "ICAR PoP …"},
      "data_quality": {"air_rh": "ok", "leaf_wetness": "proxy"}
    }
  ]
}
```

Every flag carries its reasons, the evidence tier, the data quality, and whether a leaf-wetness **proxy** was
used. That is needed for trust (farmers) and auditability (researchers).

## 5. Phenomic model ↔ KG

- `GET /v1/features/varieties/{id}` → per-disease susceptibility scores (0–1) + tiers, maturity class.
- `GET /v1/priors?field_id=&at=` → `P(disease | variety, stage, recent weather, zone)` for the 17 disease IDs.
  Fused with classifier outputs: `posterior ∝ classifier_prob × prior`, with evaluation reported as ΔF1/ΔECE.
- The model's labels use disease IDs from `diseases.yaml`. Add a `healthy` class plus the growth-stage BBCH if it
  predicts stage.

## 6. Hardware notes from the prototype review (2026-09-25)

1. **RH mismatch:** AHT20 81.2% vs BME280 71.9%. Put the primary air sensor in a radiation shield outside the
   electronics enclosure, and run a side-by-side calibration (or a salt test) before collecting research data.
2. **No leaf-wetness or rain sensor.** These are replaced by derived proxies (`rh_ge_90_h`, `est_leaf_wet_h`,
   `soil_wetting_event`) and weather-API rainfall. The proxies are validated in Phase 8 and reported as such.
3. **NPK readings** from the multi-parameter probe are indicative only. Validate them against lab soil tests
   before any use beyond "relative trend".
4. **EC "raw":** confirm the scaling/units (µS/cm) from the SN-3002 datasheet and record it in `sensors.yaml`.
5. **Sampling:** a 2-second soil probe poll adds no information and costs power. 60 s for soil, 10 s for air,
   with 1-minute aggregates uploaded, is enough.
