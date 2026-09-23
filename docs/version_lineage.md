# Version Lineage

> Current production values are **normative**. Everything else below is
> history. Historical phase documents (`backend/docs/phase*.md`) and legacy
> regression tests intentionally pin old values — they are records, not
> contradictions.

## Current production (normative)

| Line | Current | Source of truth |
| --- | --- | --- |
| Dataset | `f1-dataset-v1.3` | `data/manifests/f1-dataset-v1.3.json`, `metadata_service` |
| Dataset hashes | races `2cce529c`, results `112c8475`, laps `ac13fa1f` | frozen manifest (`sha256(bytes)[:8]`) |
| Engine | `raceengine-v2.2.0` | `app/simulation/version.py` |
| Model | `0.9.0` | `app/simulation/version.py` |
| Simulation | `9.2.0` | `app/simulation/version.py` |
| Calibration | `calibration-v1.0.0` (unchanged — no auto-promotion) | `metadata_service`, promotion gates |
| Scenario / replay / counterfactual / sensitivity | `scenario-v1`, `replay-v1`, `counterfactual-v1`, `sensitivity-v1` | `version.py` |
| Weather / calibration | `weather-v1`, `weather-calibration-v1` | `version.py` |
| Race control / policy | `racecontrol-v1`, `racecontrol-policy-v1` | `version.py` |
| Strategy | `strategy-v1.1.0` (pit-loss channel, default 0 = legacy) | `version.py` |
| Setup | `setup-v1.0.0` | `version.py` |
| Config schema | `1.0.0` | `version.py` |

## Dataset lineage

```text
f1-dataset-v1.0 → f1-dataset-v1.1 (backbone; still referenced by hashes)
  → f1-dataset-v1.2 → f1-dataset-v1.3 (frozen 2026-09-20, parent v1.2)
```

`registry.json` holds every entry with parent links, coverage, counts, and
hashes. Backbone `UNCHANGED_FROM_V1.1` per the frozen manifest.

## Engine lineage (production path)

```text
v1.0.0 (v14, reference) → v1.1.0 (v15, optimized) → v1.2.0 (v16, +tyre)
→ v1.3.0 (v17, +weather) → v1.4.0 (v18, +race-control)
→ v1.5.0 (v19, +strategy) → v2.0.0 (v20, +setup)
→ v2.1.0 (v21, +scenario) → v2.2.0 (v22, +replay/pit-loss/vectorized)
→ core/race_engine.py (current production, imports version.py)
```

`race_engine_v14..v22` under `app/simulation/` are LEGACY snapshots kept
for regression tests and old benchmark scripts. Production imports
`app.simulation.core.race_engine.RaceEngine`.

## Model lineage

`0.2.0` (phase 9 bridge) → `0.3.0` (tyre) → `0.4.0` (weather) →
`0.5.0` (race control) → `0.6.0` (strategy) → `0.7.0` (setup) →
`0.8.0` (scenario) → **`0.9.0`** (pit-loss channel; default reproduces
legacy exactly). Phase tests pin each bump (`test_version_bump*`); current
code asserts `0.9.0`.

## Simulation lineage

`8.4.0` → `8.5.0` → `9.0.0` → `9.1.0` → **`9.2.0`**
(Phase 22 replay + counterfactual validation + pit-loss channel).

## Known stale references (fixed in Phase 33)

- `VectorizedMonteCarlo` provenance and the chunked Monte Carlo branch
  claimed `raceengine-v1.4.0` / `0.5.0` / `f1-dataset-v1.1` — corrected to
  current (math untouched; see audit A1).
- `scenario/compiler._versions()` fallbacks claimed `0.8.0` / `v2.1.0` /
  `strategy-v1.0.0` — corrected to current (see audit A2).
- Legacy modules/tests pinning old values were deliberately **not**
  touched (they record history).

## Open drift (documented, not changed)

- `core/settings.py:SIMULATION_MODEL_VERSION = "0.1.0"` (== app release
  `0.1.0`, surfaced by `/health`) vs production model `0.9.0` — naming
  confusion between *application* and *model* versions (audit B1).
