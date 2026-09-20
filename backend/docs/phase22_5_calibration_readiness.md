# Phase 22.5 — Calibration Readiness

Records: `backend/data/calibration_candidates/*.json` (9 files). No
recalibration was performed; no coefficient changed. Promotion gate verdicts
are in `external_acquisition_manifest.json → promotion_gate`.

| Variable | n | years/circuits/drivers | confounders | candidate model | tier |
|----------|---|------------------------|-------------|-----------------|------|
| `pit_loss` | 235 | 2024 / 5 / 20+ | stationary-vs-lane split absent in Jolpica; fuel; traffic | empirical per-circuit distribution (NOT mean-only) | LIMITED candidate |
| `tyre_degradation` | 1129 | 2024 / 1 / 20 | compound unknown for Jolpica laps; fuel proxy; traffic; weather | lap_time ~ tyre_age_proxy + fuel_proxy + driver + circuit | LIMITED candidate |
| `weather_lap_effect` | 301 | 2024 / 6 / — | reanalysis ≠ sensor; no track-temp pre-2023 | lap_time ~ air_temp + rainfall + wind (session-aligned) | LIMITED candidate |
| `sector_pace` | 1127 | 2024 / 1 / 20 | single circuit | sector pace decomposition | LIMITED candidate |
| `driver_pace` | 1129 | 2024 / 1 / 20 | single circuit; fuel/tyre confounded | driver random effects on lap time | LIMITED candidate |
| `SC_probability` | 71 | 2024 / 1 / — | single race; free-text taxonomy | P(SC\|incident) empirical rate — **insufficient N, NOT calibrated** | PRIOR_ONLY |
| `VSC_probability` | 71 | 2024 / 1 / — | single race | P(VSC\|incident) empirical rate — **insufficient N, NOT calibrated** | PRIOR_ONLY |
| `qualifying_pace` | 0 | — | no new quali sessions | none | PRIOR_ONLY |
| `circuit_effect` | 0 | — | single-circuit acquisition | none | PRIOR_ONLY |

## Fuel confounding (§24)

Acquired lap data *permits* a fuel-effect study design
(`lap_time ~ tyre_age + compound + fuel_proxy + traffic + weather + circuit
+ driver`: fuel_proxy = lap_number/race-distance fraction, compound from
OpenF1 stints joined on lap ranges) but this phase deploys **no coefficient**:
single-circuit N, unjoined stint→lap mapping, and traffic unobserved mean the
design is identified as future work, not executed. Explicitly: fuel effects
remain confounded/PRIOR_ONLY.

## Promotion gate summary

Candidates for LIMITED **in observed era 2022–2026 only**: lap_timing,
pit_timing, tyre_compound, tyre_age, weather, race_control, sector_timing.
Refused: telemetry (0 obs), setup/strategy (NON_IDENTIFIABLE, no source).
Nothing was promoted to canonical — staging only, by design.
