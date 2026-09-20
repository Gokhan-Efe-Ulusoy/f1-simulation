# Phase 22 — Historical Data Audit

*Canonical dataset `f1-dataset-v1.1` (manifest `backend/data/manifests/dataset-manifest.json`). No historical values are fabricated; non-identifiable quantities are recorded as such.*

## 1. Coverage (dataset manifest)

- Races: 1172, Results: 26228, Circuits: 99, Drivers: 1457, Constructors: 236
- Qualifying: 26998, Pit stops: 1000 (canonical `pit_stops.json`; parquet mirrors the set)
- Earliest season: 1950, Latest: 2026-09-18-relevant range (2024-bahrain used as the e2e anchor)

## 2. 2024 Bahrain ground truth (the three e2e experiments anchor on this race)

Canonical `races.json` (`2024-bahrain`):

```json
{ "race_id": "2024-bahrain", "season_id": "2024", "round": 1,
  "circuit_id": "bahrain", "date": "2024-03-02", "scheduled_laps": null }
```

- `scheduled_laps=null` -> **total_laps is NON_IDENTIFIABLE** for this race. Every replay leg documents this and falls back to the engine default `58`; shortened test legs explicitly set `race_distance.laps`.
- Results (`results.json`): 20 rows for `2024-bahrain`, each with `driver_id, constructor_id, grid_position, final_position, status, points, fastest_lap_seconds`. Observed winner: `max-verstappen` (final_position=1). Used as a **post-hoc validation target only**, never as a simulation input (verified by `build_scenario_for_race()` asserting `final_position` never appears in the serialized scenario).

Pit stops: **0 rows** for `2024-bahrain` in `pit_stops.json` (1000 rows cover only 1950s-1990s sparse examples, e.g. `1994-pacific`). So `pit_history` is `NON_IDENTIFIABLE` for this race.

## 3. What is observable pre-race vs non-identifiable

Observable (LIMITED, because qualifying + grid identities exist):

- `grid_order` (sorted `grid_position`), `drivers:driver_id/constructor_id` from results (pole-first ordering is partial when any `grid_position` is missing -> marked `grid_order:partial`).

Non-identifiable (explicit `NON_IDENTIFIABLE`, never guessed):

- Historical **weather** (no per-race weather observations in canonical)
- Historical **setup values** (no per-driver setup records; Phase 20 uses the neutral baseline)
- Historical **tyre compounds** per stint (no per-race compound history at this granularity)
- Historical **strategy / pit timing** per driver at lap resolution (the sparse pit table has no timing, and for 2024-bahrain it is empty)
- Historical **fuel load**
- Historical **driver intent / race-control intent**
- **Per-lap tyre state, sector flags, incident timing** (no per-lap source)

Weak evidence only (PRIOR_ONLY):

- Weather forecast summary (model prior `WeatherEngine(as_of)`, never a claim about realized weather)
- Setup tyre-interaction load/warmup effects (explicit `NON_IDENTIFIABLE` tyre evidence in `SetupEffects`)

## 4. Leakage control

All calibration reads go through `calibration_api*(as_of)` with `strict_before` (all source timestamps must be `< as_of = race_date - 1 day`). Walk-forward probes record `training_end` / `target_date` / `observations_used` / `observations_excluded` and adversarial future-injection probes (`future_result`, `realized_weather`, `observed_pit`, `final_standings`) must leave outputs bit-identical (1e-12).

## 5. Eras

Strategy tyre-model is inert pre-2023 in the vectorized path (pit/compound legs are recorded in provenance but have no pace effect). Behaviour is era-flagged `UNKNOWN` for setup interventions on pre-2022 seasons (allowed as model dials, flagged honest).

## 6. Files inspected for this audit

- `backend/data/canonical/races.json`, `results.json`, `pit_stops.json`, `qualifying.json`
- `backend/data/manifests/dataset-manifest.json`
- `backend/app/data/scenario.py` (`build_scenario`)
- `backend/app/simulation/replay/state_builder.py`, `historical_observer.py`
