# Phase 16 Tyre Data Audit

**Date:** 2026-09-10  
**Dataset:** `f1-dataset-v1.1` (1172 races, 26228 results) + `f1db v2026.13.0` + `OpenF1` + `FastF1 3.8.3`

## 1. Sources Inspected

| Source | Location | Compounds | Tyre Age | Stint | Lap Times | Pit Stops | Notes |
|---|---|---|---|---|---|---|---|
| **Jolpica** | `backend/data/raw/jolpica/{season}/{round}/pitstops.json` (e.g., `2024/1/pitstops.json` 20 rows) | **No** | **No** | **No** (only lap, duration, time) | **No** (separate results) | **Yes** (lap, duration) | Pit only, no compound |
| **F1DB** | `backend/data/raw/github/f1db/v2026.13.0/f1db-races-pit-stops.csv` 22490 rows | **No** (only `tyreManufacturerId` goodyear/pirelli) | **No** | **No** | **No** | **Yes** (stop, lap, time) | No compound |
| **OpenF1** | `backend/data/raw/openf1/2023/7953/laps.json` + stints via `https://api.openf1.org/v1/stints?session_key=7953` | **Yes** (`SOFT` 0-12 laps) | **Yes** (`tyre_age_at_start`) | **Yes** (`lap_start, lap_end, stint_number`) | **Yes** (`lap_duration` + sectors) | **Yes** (via stints) | **Modern only (2023-26)** |
| **FastF1** | `backend/data/raw/fastf1/cache/2024/...` `laps` DataFrame | **Yes** (`SOFT`/`HARD`, `TyreLife`) | **Yes** (`TyreLife`) | **Yes** (inferred via `PitInTime/Out`) | **Yes** (`LapTime`) | **Yes** | **Modern only (2018+, verified 2024 Bahrain 20 drivers)** |
| **Canonical** | `backend/data/canonical/pit_stops.json` 1000 rows | **0%** (`compound samples 0`) | **No** | **No** | **No** | **Yes** | Only lap+time, no compound |
| **Simulation** | `backend/app/simulation/tyre/model.py:1` | **Yes** (SOFT/MEDIUM/HARD/INTER/WET) | **Yes** (`age_laps, stint_lap`) | **Yes** (`TyreState`) | **No** (uses lap_time model) | **Yes** | Physics-based, not calibrated |

**Conclusion:** Direct tyre compound + age + stint is **only available for modern Pirelli era 2023-2024** via OpenF1/FastF1. Historical 1950-2022 has **no compound/age** in any audited source (Jolpica, F1DB, canonical).

## 2. Compound Normalization Audit

**Source-native values:**

- OpenF1: `SOFT`, `MEDIUM`, `HARD` (uppercase)
- FastF1: `SOFT`, `HARD` (also `MEDIUM`, `INTERMEDIATE`, `WET` where applicable)
- f1db/Jolpica: `tyreManufacturerId` not compound

**Canonical taxonomy proposed (after inspection):**

```
SOFT
MEDIUM
HARD
INTERMEDIATE
WET
UNKNOWN
```

Aliases to normalize (only where mapping is justified, preserve source):

- `SOFT`, `SOFT TYRE`, `C5`, `C4` → `SOFT` (modern Pirelli C5 softest)
- `MEDIUM`, `C3` → `MEDIUM`
- `HARD`, `C2`, `C1` → `HARD`
- `INTERMEDIATE`, `INTER` → `INTERMEDIATE`
- `WET`, `FULL WET` → `WET`

**Historical compatibility:** Do NOT map historical `goodyear`/`pirelli` to modern compounds. Historical eras (1950-60) had no compound categories in data → `UNKNOWN` or `NON_IDENTIFIABLE`.

**Storage:** Both `source_compound` and `canonical_compound` retained, provenance hash preserved.

## 3. Stint Reconstruction

**Logic:**

```
race start → initial tyre (unknown unless stint lap_start=1)
pit stop (lap N) → new stint (stint_number+1)
```

**Handling:**

- Pit known, compound unknown → `stint_boundary available, compound null`
- Compound known, lap unavailable → `compound available, lap_time unavailable`
- Nothing → `available false`

**Reconstructable stints:**

- Modern (2023-24) with OpenF1/FastF1: **Yes** (lap_start, lap_end, compound, tyre_age_at_start)
- Historical (1950-2022) with only pit lap: **Partial** (boundary yes, compound null, age reconstructed as `current_lap - stint_start` but documented as reconstructed)

## 4. Lap Coverage

- **1950-2010:** `NOT_AVAILABLE` (no lap_duration in any source)
- **2011-2022:** `NOT_AVAILABLE` (f1db/jolpica no lap, OpenF1 404, FastF1 not cached)
- **2023-2024:** `FULL` via OpenF1 (99s lap_duration) and FastF1 (soft/hard + TyreLife)
- **2025-2026:** `PARTIAL` (2024 verified, 2025-26 not yet fetched but API supports)

## 5. Evidence Tiers

```
OBSERVED: Directly in OpenF1/FastF1 stints (SOFT, tyre_age_at_start)
CALIBRATED: Estimated from 2023-24 lap+compound (degradation slope)
LIMITED: 2023-24 only (2 seasons, not 1950-2026)
PRIOR_ONLY: 1950-2022 tyre (no data, use prior)
NON_IDENTIFIABLE: Historical compound, warm-up, cliff (insufficient)
```

## 6. Tyre Eras

**Determined from data:**

- `TYRE_ERA_HISTORICAL` 1950-2010: No compound data → `NON_IDENTIFIABLE`
- `TYRE_ERA_PIRELLI` 2011-2026: Has SOFT/MEDIUM/HARD (but only 2023-24 observed) → `LIMITED` (2011-22 prior_only, 2023-24 calibrated)

Do not force single model across eras.

## 7. Reproducibility

Audit script: `python -m scripts.phase16_data_audit` (to be created) regenerates this file from `backend/data/raw` and `backend/data/canonical`.

**Hashes:**
- f1db zip SHA256 `82a5102e1157a409`
- OpenF1 stints `session_key=7953` hash (via provenance)
- FastF1 cache `backend/data/raw/fastf1/cache`

## 8. Summary for Phase 16

- **Sufficient for calibration:** 2023-24 Pirelli era with ~4000 laps + stints (enough for linear degradation, compound effect limited).
- **Insufficient:** Historical 1950-2022, warm-up (out-lap), cliff (need >30 laps per stint with degradation).
- **Action:** Build stint reconstruction for modern, calibrate simple linear degradation `Δ = β1*age`, hierarchical shrinkage, fallback to prior for historical.

**No fabrication:** All missing `null` with `available false`.
