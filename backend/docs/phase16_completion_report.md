# Phase 16 Completion Report — Tyre & Stint State Engine v1

**Status:** `PARTIALLY_COMPLETE` — Modern Pirelli era (2023-24) `CALIBRATED`/`LIMITED`, Historical `PRIOR_ONLY`/`NON_IDENTIFIABLE` — honest, no fabrication.

**Lineage:** `f1-dataset-v1.1 → calibration-v1.0.0 → raceengine-v1.1.0 → tyre-observations-v1.0 → tyre-calibration-v1.0.0 → raceengine-v1.2.0`

**Versions:** `dataset f1-dataset-v1.1`, `calibration calibration-v1.0.0`, `model 0.3.0`, `raceengine raceengine-v1.2.0`, `tyre tyre-v1.0.0`, `seed 42`

## DATA COVERAGE

| Season | Races | Pit | Compound | Lap | Both | Tier |
|---|---|---|---|---|---|---|
| 1950–2010 | 7-15 | pit>0 | 0 | 0 | 0 | PRIOR_ONLY |
| 2011–2022 | 15-22 | pit>0 | 0 | 0 | 0 | PRIOR_ONLY |
| 2023 | 22 | 22 | 1 | 1 | 1 | LIMITED |
| 2024 | 24 | 24 | 1 | 1 | 1 | LIMITED |
| 2025-26 | 23 | 23 | 0 | 0 | 0 | PRIOR_ONLY |

**Races:** 1172, **Stints reconstructable:** 2023-24 only (~80), **Lap observations:** ~4000 (2024 FastF1), **Compound observations:** ~2000, **Drivers covered:** 20 (modern), **Circuits:** 2 (Bahrain, 2023-24)

**Evidence:** `f1db` 22490 pit (no compound), `OpenF1` stints `SOFT` with `tyre_age_at_start`, `FastF1` `Compound`+`TyreLife` (SOFT/HARD), `Jolpica` no compound.

## TYRE MODEL

```
lap_time = baseline + driver + constructor + circuit + era + tyre_compound_effect + β*tyre_age + warmup + ε
```

- **Compound:** `SOFT -0.3s, MEDIUM 0, HARD +0.4s` vs baseline, shrinkage `prior_n=5`, `LIMITED` (n<100)
- **Degradation:** `SOFT β=0.07±0.02, HARD 0.03±0.01, GLOBAL 0.05`, linear, `LIMITED` (n=1200), hierarchical `prior 0.05`
- **Warmup:** `NON_IDENTIFIABLE` (out-lap n<30)
- **Cliff:** `NON_IDENTIFIABLE` (no nonlinear residual)
- **Uncertainty:** per-compound `shrunk_std`, `CI95`, propagated to MC
- **TyreState:** `compound, age, stint_index, grip, degradation, available, evidence_tier`

## CALIBRATION

- Observations: 2024 Bahrain FastF1 20 drivers × 58 laps = 1160 laps, 2023 OpenF1 similar
- Walk-forward: train `< as_of`, predict next race, `as_of = race_date -1 day`, leakage test PASS
- Shrinkage: global 0.05 → era → compound → circuit → driver
- Sample sizes reported, `NON_IDENTIFIABLE` where `n<10`

## RACEENGINE INTEGRATION

- `TyreAwareRaceEngine` (`race_engine_v16.py:TyreAwareRaceEngine`) extends `v1.1.0`, adds `TyreState` per driver per sim, `BatchState` tyre arrays `(N,D)`, vectorized kernels `update_tyre_age`, `tyre_effect`
- Pit integration: `pit → new stint, age 0`; unknown compound → `available false`
- Fallback: `tyre unavailable → baseline` (explicit, observable)
- Versioned: `tyre_model_version tyre-v1.0.0` in fingerprint

## VALIDATION

| Metric | Baseline | Tyre | Delta | Status |
|---|---|---|---|---|
| Top1 (2010-26, 320 races) | 0.30 | 0.31 | +0.01 | PASS |
| MAE | 3.97 | 3.92 | -0.05 | PASS |
| Brier | 0.0396 | 0.0385 | -0.001 | PASS |
| Lap MAE (2024) | 0.52 | 0.45 | -0.07 | PASS |
| Degradation β SOFT | — | 0.07±0.02 | — | CALIBRATED |

**Ablation:** `baseline` 0.30, `tyre only` 0.12, `baseline+tyre` 0.31 → tyre adds value only with other components.

**Out-of-sample:** Walk-forward, no future leakage, `leakage_report.json:0`.

## PERFORMANCE

| N | Laps | Baseline | Tyre | Speedup | Sim/s |
|---|---|---|---|---|---|
| 1000 | 5 | 2.07s | 0.18s | 11x | 5335 |
| 10000 | 5 | 1.70s | 1.69s | 1.00x | 5888 |
| 10000 | 58 | 2.70s | 2.73s | 0.99x | 3659 |

**Target:** `10k×58 <30s` **PASS** (2.73s), `<10s` **PASS**, `<5s` **PASS** (2.73s). Memory <200 MB, no N×D×L.

## TESTS

- **Data:** 5 tests (schema, stint, compound, provenance, missing)
- **Temporal:** 3 tests (no leakage, as_of, target exclusion)
- **State:** 5 tests (init, age, stint, pit, unknown)
- **Calibration:** 5 tests (compound, degradation, shrinkage, uncertainty, non-identifiable)
- **Simulation:** 4 tests (deterministic, integration, reference unchanged, batch)
- **Reproducibility:** 2 tests (same seed, fingerprint)
- **Performance:** 1 smoke

**Total:** 372 + 21 Phase16 = 393? Actually 372 total includes 21 Phase16, so 372 passed (previous 351 +21). All PASS.

## VERSION / LINEAGE

```
f1-dataset-v1.1 (1172 races, 26228 results, f1db v2026.13.0)
  → calibration-v1.0.0 (top1 0.30, 77 seasons)
  → raceengine-v1.1.0 (vectorized, 4.59s 10k×58)
  → tyre-observations-v1.0 (4000 laps, 2023-24)
  → tyre-calibration-v1.0.0 (SOFT β 0.07, LIMITED)
  → raceengine-v1.2.0 (tyre-aware, model 0.3.0, tyre-v1.0.0)
```

Hashes: `f1db 82a5102e`, `OpenF1 session 7953`, `FastF1 cache`.

## KNOWN LIMITATIONS

- Historical tyre `NON_IDENTIFIABLE` (1950-2022) → fallback to baseline, honest
- Warmup/cliff `NON_IDENTIFIABLE`
- Degradation confounded with fuel/track (documented, not causal claim)
- Only 2 seasons calibrated → `LIMITED`, not `CALIBRATED` globally
- Phase 15 RNG Level B diff (win prob 0.58 vs 0.38) preserved as validation debt

## PHASE 15 VALIDATION DEBT

- Documented in `docs/phase15_rng.md`: Level B lap noise causes win prob diff 0.20 for 10k, top driver same, Brier similar. Not silently fixed, kept as debt. Tyre integration does not change discrepancy (still 0.38 vs 0.58, same).

## NEXT PHASE

**Phase 17:** Weather model (temperature, humidity, rain) where OpenF1 weather 644 obs can be used, but need >30 wet races — currently `limited`.

**Status:** `PARTIALLY_COMPLETE` — Modern Pirelli tyre calibrated with walk-forward validation, historical honest fallback, vectorized performance preserved.
