# Phase 19 Data Audit — Strategy

**Version:** strategy-v1.0.0  **Date:** 2026-09-17
**Upstream:** f1-dataset-v1.1, calibration-v1.0.0, tyre-v1.0.0, weather-v1.0.0, racecontrol-v1.0.0

## 1. Historical Strategy Observations

| Source | Fields | Coverage | Tier |
|--------|--------|----------|------|
| `data/canonical/races.json` `results.json` | finishing order, laps completed, status | 1950-2024 ~1100 races | OBSERVED for result |
| `data/tyre/observations` via `tyre/calibration.py` | stint compound/age per lap via FastF1 2024 Bahrain | ~200 stints (SOFT/HARD n≥30) | CALIBRATED SOFT/HARD, MEDIUM PRIOR_ONLY |
| `data/canonical/lap_times.json` (?) sparse | lap times per driver | 1996+ partial, 2023+ richer | LIMITED for pit lap exactness |
| `data/raw/openf1/**/laps` `pit` | pit entry/exit timestamps, compound | 2023-2026 ~4-6 races | LIMITED |
| Historical pit strategy timeline (full sequence 1-stop vs 2-stop per race) | Not in `canonical` — would require `data/strategy.json` which does not exist | 0 | NON_IDENTIFIABLE |
| Weather forecast historical accuracy | Not stored; only realized weather via OpenF1 | - | NON_IDENTIFIABLE |
| Race-control pit window історичні | No `race_control.csv` with SC pit decisions | - | NON_IDENTIFIABLE |
| Fuel per lap historical | No `fuel` telemetry for 1950-2022 | - | NON_IDENTIFIABLE (con founding) |
| Team orders historical | No team order logs | - | NON_IDENTIFIABLE |

**Search performed:** `grep -r "pit|strategy|compound|stint" data/` `glob **/strategy.csv` `grep "available_sets" app/` — none beyond in-code DTOs.

## 2. Calibration Authoritative Values (Phase 17.1 audit)

Do NOT use stale SOFT +0.07. Current `tyre/calibration.py:calibrate_degradation`:

```
SOFT: beta ≈ -0.2229 ±0.038  n=~45  LIMITED (but available)
HARD: beta ≈ -0.20185 ±0.024 n=~38  LIMITED
MEDIUM: insufficient n<30  PRIOR_ONLY (no beta)
```

Note sign: original spec said +0.2229, but engine stores positive beta for time loss per lap; value magnitude ~0.20 sec per age. We keep through calibration loader, not hard-coded.

Any new strategy code loading via `TyreStrategyEngine.beta_for` respects `as_of` filter — verified not hard-coded.

## 3. Freshness / Fabrication Guardrails

* No synthetic `strategy_history` inserted into `races.json`.
* Candidate generation uses only `available_compounds` from `state` (not future compound).
* Evidence tier defaults `PRIOR_ONLY` for all strategy decisions where n<30 or no observation.
* Forecast uncertainty `0.15` prior not calibrated.
* Opponent pit prob `0.09` Beta(2,20) prior not calibrated.

## 4. Coverage by Strategy Dimension

| Dimension | Historical n | Tier |
|-----------|--------------|------|
| Pit lap exactness | ~20 races with pit timestamps 2023-24 | LIMITED |
| Compound selection per stint | ~200 stints 2024 Bahrain only | LIMITED for S/H, PRIOR_ONLY M |
| Stint length error | same | LIMITED |
| Strategy class agreement (1-stop vs 2-stop) | Would need per-race label, not present | NON_IDENTIFIABLE |
| Undercut gain | Needs per-battle telemetry, not present | NON_IDENTIFIABLE |
| SC pit response | Needs SC laps vs pit logs correlated, not present | NON_IDENTIFIABLE |
| Weather crossover timing | Needs wet races n≈2 with flag+compound | NON_IDENTIFIABLE |

## 5. Lineage

```
FastF1 tyre observations (2024 Bahrain) -> calibrate_degradation(as_of) -> beta -> StrategyState.estimated_degradation -> Candidate evaluation -> Decision -> Outcome
OpenF1 weather (644 rows) -> WeatherState -> forecast_summary -> weather_strategy (PRIOR_ONLY) -> Decision
OpenF1 raceControl? absent -> policy prior -> RaceControlEngine -> pit_window RC cheap -> Decision
```

All `as_of` strict_before ensures no future observations enter calibration.

## 6. Missing Historical Limitations (must preserve)

* Historical tyre compound coverage limited (pre-2011 not Pirelli, no compound labels).
* Weather coverage limited pre-2023.
* Race-control observations limited.
* Many strategy parameters PRIOR_ONLY.
* Warmup/cliff NON_IDENTIFIABLE — not used in window calc beyond optimal.
* Fuel confounding remains (fuel mass in DriverState but not historically observed per lap).
* Opponent behavior weakly calibrated (no opponent policy fit).
* Pit strategy data incomplete (no full per-race timeline).

These are documented not hidden.

## 7. Recommendation

To move any strategy dimension to CALIBRATED, need `data/strategy.csv` with per-race per-driver `strategy_id, stints:[{compound,laps,pit_lap}], pit_reason, SC lap, weather lap` for n≥30 per circuit × season. Until then keep PRIOR_ONLY.
