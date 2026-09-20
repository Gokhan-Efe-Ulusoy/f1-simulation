# Phase 18 Data Audit — Race Control Coverage

**Version:** `racecontrol-v1.0.0`  **Date:** 2026-09-17
**Dataset:** `f1-dataset-v1.1` (races 2cce529c, results 112c8475, tyre 503079ee)
**Calibration:** `calibration-v1.0.0` driver `3df26222`

## 1. Historical Race-Control Observations (searched repo `data/canonical/*.json`, `app/simulation/*`)

| Source | Fields available | Coverage | Evidence tier |
|--------|----------------|----------|---------------|
| `canonical/races.json` | race_id, season, round, date, circuit, laps, distance, results → positions, status (`finished`, `retired`, `crash`) | 1950-2024 ~ 1000 races | `OBSERVED` for positions/status; `NON_IDENTIFIABLE` for flags |
| `canonical/results.json` | driver_id, final_position, points, status, laps completed | same | `OBSERVED` for finish/DNF |
| `data/raw/openf1/2023-2026/**/weather.json` | air/track temp, humidity, pressure, rainfall, wind | ~644 rows (4 sessions) | `LIMITED` |
| `app/simulation/core/events.py` | 30+ EventType (SAFETY_CAR etc.) but no historical flag timeline dataset | schema only | `NON_IDENTIFIABLE` for historical flag timeline |
| `app/simulation/models/incident.py` | incident severity distribution `0.50/0.30/0.15/0.05` (prior) | config | `PRIOR_ONLY` |
| `app/simulation/racing/*` | battle/drs/restart models, no flag ground truth | model | `PRIOR_ONLY` |

**Result:** No `safety car laps`, `VSC deployments`, `sector yellow timestamps`, `red flag periods`, `formation lap incidents`, `restart gaps` historical timeline in the repo. Any such data would be under `data/raw/openf1/*/raceControl.json` or `data/canonical/flags.json` — not present.

## 2. What Was Searched

```
glob **/*.json  -> races, results, lap_times sparse 1950-1970 missing
grep -r "safety car|VSC|yellow|red flag|race_control|flag" app/
grep -r "SC|VSC" data/
```

No matches beyond in-code event definitions. Therefore all race-control **coefficients** and **historical frequencies** remain `PRIOR_ONLY` or `NON_IDENTIFIABLE`.

## 3. Fabrication Policy

* No synthetic flag timelines inserted into `races.json` / `results.json`.
* Wetness → incident multiplier `1+wet*0.6` marked PRIOR_ONLY (spec explicitly forbids claiming `rain causes accident` without evidence).
* Neutralisation tables `1.40 SC`, `1.25 VSC`, pit `0.35 SC` etc. explicitly `PRIOR_ONLY` with comment `not empirically calibrated`.
* Where observation missing, `unknown` returned (fallback prior dry, not fabricated wet races).

## 4. Coverage by Era

| Era | Seasons | Flag data | Weather | Tyre | Incident flag coupling |
|-----|---------|-----------|---------|------|------------------------|
| 1950-1970 | ~200 races | `NON_IDENTIFIABLE` | `NON_IDENTIFIABLE` | `NON_IDENTIFIABLE` | `PRIOR_ONLY` (dry prior) |
| 1971-1990 | ~300 races | `NON_IDENTIFIABLE` | `NON_IDENTIFIABLE` | `NON_IDENTIFIABLE` | `PRIOR_ONLY` |
| 1991-2008 | ~300 races | `NON_IDENTIFIABLE` | `NON_IDENTIFIABLE` | `NON_IDENTIFIABLE` | `PRIOR_ONLY` |
| 2009-2013 | ~95 races | `NON_IDENTIFIABLE` | `PRIOR_ONLY` (no OpenF1) | `NON_IDENTIFIABLE` | `PRIOR_ONLY` |
| 2014-2021 | ~160 races | `LIMITED`* if scrape but not present | `PRIOR_ONLY` | `LIMITED` tyre? | `PRIOR_ONLY` |
| 2022-2024 | ~66 races | `LIMITED` (4 sessions via OpenF1 raceControl if fetched) | `LIMITED` (644 rows) | `CALIBRATED` Bahrain 2024 | `PRIOR_ONLY` |

*LIMITED not OBSERVED because n<30 per circuit for flags even if OpenF1 holds control messages, insufficient for calibration.

## 5. Identifiability Assessment

* `race_control_model_version` — `NON_IDENTIFIABLE` historically, `PRIOR_ONLY` prospectively.
* `vsc_probability` etc. — `NON_IDENTIFIABLE` (sample size trivial).
* `wetness_threshold -> red_flag` — `PRIOR_ONLY` (extreme wet races n≈2).
* All `evidence_tier` fields in `RaceControlSnapshot`, `RaceEvent`, `NeutralisationFactors` default `PRIOR_ONLY`.

## 6. Lineage

```
raw/openf1 weather.json (644) -> WeatherState -> RaceControlPolicy (prior) -> (N,L) phase via RNG 600 -> LapTime/Position -> Outcome
                                    ^
                                    no historical SC labels used
```

No future leakage: `WeatherEngine` filters `date < as_of`; `RaceControlEngine` uses isolated RNG 600, not peeking future `phase[t+1]`.

## 7. Recommendation

Acquire `OpenF1 raceControl & trackStatus` streams for 2023-2026 to estimate per-circuit yellow/SC rates before claiming `CALIBRATED`. Until then keep `PRIOR_ONLY`.
