# Smart Soil Advisory Platform (Egypt)

An **advisory-only, sensors-only** smart soil monitoring and crop-optimisation system, built from the
*Smart Agricultural Soil Analysis, Hardware & Software System Master Specification*.

An ESP32 field node reads dual-depth soil probes and a canopy weather station and sends data **one way** to the
web app. The app fuses the readings with the seasonal lab profile, ranks the 10 Egyptian crops, and tells the farmer
exactly what to add (amendments, irrigation and leaching water, Tank A/B/Acid fertigation, chelates, vitamins and
biofertilizers). It never switches valves, relays or pumps.

## Quick start

**Double-click `run.bat`.** It starts the app and opens <http://127.0.0.1:8000> in your browser. Keep its window
open while you use the app, and close it to stop. Running `python run.py` does the same thing.

The first run creates `.venv` and installs the requirements, so it needs internet and takes about a minute. API docs
are at `/docs`. If the app is already running, `run.bat` just opens the browser.

| Command | What it does |
|---|---|
| `python run.py` | Start the web app (SQLite database at `data/smart_soil.db`) |
| `python run.py --host 0.0.0.0` | Expose the app on the LAN so a real ESP32 node can post to it |
| `python run.py --test` | Run the automated test suite (142 tests) |
| `python run.py --hardware-pdf` | Regenerate `docs/Hardware_BOM_Wiring_Firmware.pdf` |

**Try it without hardware:** open **Simulator Lab**, pick *Zone B — Simulator Sandbox*, then click a spec case (R1–R6) or
**Generate Random Input & Test Now**. The dashboard, crop ranking, alerts and prescription all update live over SSE.

To start over with new data, press **↺ Reset zone data** (on the Dashboard, Lab and Simulator pages, or call
`POST /api/v1/zones/{id}/reset`). It clears the selected zone's readings, alerts, saved prescriptions and lab profile; you
can untick any of these. The zone, its crop settings and its devices are kept.

The seeded device `EGY-NODE-001` gets an API token on first start. The token is printed in the console and saved to
`data/seed_device_token.txt`.

## What is where

```
run.py                     one-command launcher
backend/app/
  knowledge/               spec data: 10 crops (Tables 4.1–4.3), soils/regions/fertilizers (§1–2, 6.4), test cases R1–R6 (§6.5)
  engine/
    formulas.py            §7.3 formulas: VPD (Tetens), ATC EC25, AWC, FAO-29 LR, gross irrigation, Soil Health Index
    telemetry.py           §6.2 contract → validated, ATC-normalised, NPK-calibrated reading (§6.4 fault detection)
    alerts.py              Table 2.4 rules + Table 4.3 crop rules + hardware alerts (bilingual)
    matcher.py             Mode A: weighted 10-crop ranker (§7.1)
    prescription.py        Mode B: five-module "What to Add" generator (§7.2)
    fertigation.py         Tank A / B / Acid allocation + incompatibility guard
  services/                SQLite repository, ingestion, simulator, SSE, hardware PDF
  main.py                  FastAPI routes (§8.3)
frontend/                  bilingual EN / AR (RTL) single-page app, no build step, works offline
firmware/esp32_soil_node/  PlatformIO ESP32 / ESP32-S3 sensors-only firmware
docs/                      Hardware BOM, Wiring & Firmware Code PDF
tests/                     pytest suite (§9 item 8: formulas, tanks, rules, crops, ranking, 60-input fuzz, API)
```

### Spec mapping

| Spec | Implementation |
|---|---|
| §6.2 JSON contract | `POST /api/v1/telemetry/ingest` (token in the `X-Device-Token` header or as a Bearer token). Optional MQTT ingestion runs when `SOIL_MQTT_HOST` is set. |
| §6.4 calibration | Texture FC/PWP mapping, NPK `raw × gain + offset` (offset from 1 lab point, least squares from 2 or more), out-of-physics rejection, stuck-at-zero detection |
| §6.5 test cases | `POST /api/v1/simulator/push` (R1–R6, manual sliders); `POST /api/v1/simulator/random` (6 modes) |
| §7.1 Mode A | `POST /api/v1/optimize/match-crops` |
| §7.2 Mode B | `POST /api/v1/optimize/prescription` (prescriptions are stored and printable) |
| §8.2 schema | `backend/app/db.py` (SQLite; same column names as the spec's PostgreSQL/Timescale tables) |
| §8.4 six views | Live Dashboard · Lab Soil & Water · What to Add · 10-Crop Matcher · Simulator Lab · Alerts, Reports & Hardware |
| §6.3 hardware PDF | `GET /api/v1/hardware-guide/export?zone_id=…` (pre-filled with the zone's device ID and URL), plus `docs/` |

## Values that do not come from the spec

The spec says *"never invent thresholds"*, but it leaves out many numbers the engine needs. The main ones are below.
The reference values were written from general knowledge and have **not been checked against the original
publications**. Only some carry an **"external ref."** label in the UI. Verify them before field use.

- **Kc per stage**: FAO-56 Table 12 (mango and pomegranate use literature estimates; they are not in FAO-56).
- **Silt-loam FC / PWP** (31 % / 13 %): USDA / Saxton-Rawls typical values. §6.4 lists only 5 textures, but case R6 is silt loam.
- **Stage N-P-K soil targets, weekly fertigation rates and chelate rates**: generic fertigation guidance. Calibrate these with a local extension lab.
- **Gypsum requirement**: USSL Handbook 60 equation (ESP target 10 % from Table 1.2, efficiency factor 1.25).
- **ESP from SAR** (USSL), **dew point** (Magnus formula), **ECe ≈ 1.5 × ECw** (FAO-29), **chloride threshold** of about 142 mg/L (FAO-29).
- **Drip wetted fraction** of 0.5 (0.6 in greenhouses), used to scale corrective N-P-K doses.

### Design choices made for this project (not from the spec or a reference)

- **Crop scoring:** the spec gives the six main weights. The weights inside each dimension, the score fall-off widths,
  season and region scores, texture similarity, hypoxia and lime sensitivity classes, and the 85 / 65 tier cut-offs were
  chosen for this project.
- **Tuned against the test cases:** the moisture sub-weights, and the ×0.9 factor on orchards when water-table depth is
  unknown, were set after R6 first ranked differently from the spec. The sulfur curve (300 kg at pH 7.8 to 500 kg at pH 8.6)
  and the +5 % leaching for ECw > 1.2 were chosen to reproduce R1 and R4.
- **Alert cut-offs** the spec describes only in words (for example "low" or "high" VWC), the 2 °C dew-point spread and the
  12.0 V battery limit.
- **Compost:** 15–30 m³/feddan mapped linearly from SOM 2.0 % down to 0.5 %.

## Notes on the spec itself

- **§9, deliverable 4(d) and item 5:** the PDF text is garbled (`(, , AMF, )` and `Acid TankBacillusAzotobacterTrichoderma`).
  It was read as Tank A / Tank B / **Acid tank**, with biofertilizers *Bacillus*, *Azotobacter*, AMF and *Trichoderma*.
- **ECe:** probes measure pore-water EC, not saturated-paste ECe. The app treats the upper probe's pore EC at 25 °C as the
  live ECe, as the spec does. A seasonal lab comparison is still recommended.
- **R1 "+20 % leaching" and R4 "pause fertilizer":** in both cases ECe is *below* pomegranate's 3.5 dS/m limit. The engine
  leaches once ECe reaches 80 % of the limit (15–20 %), adds 5 % for brackish water (ECw > 1.2), and caps at 25 %.
  This gives R1 = 20 % and R4 = 24 %. Fertilizer is paused only when ECe *exceeds* the limit (§7.2). Below that, the app
  shows a "keep fertigation dilute" note instead.
- **Ranking results compared with the spec:** five of the six cases name expected crops (R2 expects alerts only).
  R1, R3, R4 and R6 rank the expected crops first. **R5 only partly matches:** grapes and mango tie at 98.3 and grapes is
  listed first only because ties sort alphabetically, while citrus, which the spec expects, ranks 4th (98.0).
  R3 scores about 100 %, above the spec's 92–97 %.
- **This is not independent validation.** The engine was tuned on these same cases, and the ranking test is lenient: it
  accepts an expected crop anywhere in the top N+2. Real accuracy needs field data the engine has not seen.

## Hardware

See `docs/Hardware_BOM_Wiring_Firmware.pdf` for the bill of materials, pin-by-pin wiring, power distribution, burial
depths per crop, flashing and calibration. To flash the node:

1. Edit `firmware/esp32_soil_node/include/config.h`: set the Wi-Fi details, `API_TOKEN` and `INGEST_URL` (your PC's LAN IP).
2. Build and upload with `pio run -e esp32-s3 -t upload` (`-e esp32-classic` targets a classic ESP32). Only
   `esp32-s3` has been compiled; neither has been run on real hardware.
3. Check the RS485 probe register map against your probe's datasheet. Vendors differ.
