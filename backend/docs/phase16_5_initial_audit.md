# Phase 16.5 Initial Audit

**Date:** 2026-09-10  
**Auditor:** Phase 16.5 hardening

## Debt Inventory

| Area | Current state | Evidence | Risk | Required action |
|---|---|---|---|---|
| **Simulator** | `RaceEngine v1.1.0` vectorized, 4.59s 10k×58, `v1.2.0` tyre-aware extends it | `backend/app/simulation/race_engine_v14.py`, `race_engine_v15.py`, `race_engine_v16.py`, `performance/vectorized_montecarlo.py` | Medium: tyre integration adds 0.05s overhead but win prob diff 0.20 vs reference | Fix RNG to Level A, validate tyre effect |
| **Race Engine** | `v1.1.0` performance-only, `v1.2.0` tyre-aware (model 0.3.0) | `version.py: RACEENGINE_VERSION raceengine-v1.2.0, MODEL_VERSION 0.3.0` | Low: version bumped correctly per spec 0.3 | Verify lineage |
| **Monte Carlo** | `MonteCarloRunner` + `VectorizedMonteCarlo` (N,D) batch, correlated constructor, AR1 0.7 | `montecarlo.py:1`, `performance/rng.py:BatchRNG` | High: RNG Level B diff 0.196 win prob | Root-cause RNG, fix to Level A |
| **Calibration** | `calibration-v1.0.0` 1400 drivers, walk-forward 2010-26 top1 0.30, Brier 0.039 | `data/calibration/models/driver_model.json:1400`, `calibration-manifest.json` | Low: 0 leakage, but tyre limited to 2023-24 | Re-run with current dataset, verify hashes |
| **Datasets** | `f1-dataset-v1.1` 77/77, 1172 races, 26228 results, `f1db v2026.13.0` fallback for 429 | `data/manifests/registry.json:7`, `data/canonical/races.json:1172` | Medium: historical tyre/lap sparse, but honest null | Audit coverage, no bump unless data changes |
| **Manifests** | `registry.json` has 7 entries, `dataset-manifest.json` for v1.1, `simulation/manifests/simulation_manifest.json` | `data/manifests/registry.json` | Low: v1.1 counts 26228 vs earlier 34856 (duplicate fix) — need to ensure v1.1 is correct | Verify counts |
| **Provenance** | Every record `source_provider, retrieval_date, raw_hash` | `data/raw/github/f1db/...provenance.json` | Low | Verify hashes |
| **Adapters** | Jolpica (0.5 req/s, Retry-After), OpenF1 (2023-26), FastF1 3.8.3 (2024 Bahrain), F1DB (pinned), FIA/Official NOT_AVAILABLE | `app/data/sources/*.py` | Medium: Jolpica 429 recovered via F1DB, but need to document BLOCKED vs NOT_AVAILABLE | Audit source coverage |
| **Tests** | 372 passed (351 +21 Phase16) + 10 performance isolated = 382 total, but default suite reports 372 | `backend/tests/test_phase16_tyre.py:21` | Medium: test-count inconsistency in reports (372 vs 382 vs 393) | Accurate accounting per workstream R |
| **Benchmarks** | `phase15_baseline.json` (7.93s 10k×5), `phase15_final.json` (4.59s 10k×58), `phase16_benchmark.json` (tyre 2.73s) | `data/simulation/benchmarks/` | Low: numbers are actual, but need final 10k×58 for tyre | Re-run final benchmark |
| **Documentation** | `phase15` docs exist, `phase16` 4 docs, but `phase16_data_audit.md` says tyre 2023-24 only | `docs/phase16*.md` | Low: need to preserve historical reports, update current | Cleanup stale refs |
| **Stale refs** | `f1-dataset-v1.0` still in code comments, old `MODEL_VERSION 0.2.0` in some docs, test counts 305 vs 372 | `grep -r "f1-dataset-v1.0" backend/docs` | Low: need to mark historical, update current | Search and update |

## Stale Reference Search

- `f1-dataset-v1.0` appears in `phase12` docs as parent — **preserve as historical**, not delete.
- `raceengine-v1.0.0` appears in `phase14` docs — **preserve**.
- `MODEL_VERSION 0.2.0` in `phase15` docs — **update to 0.3.0** for Phase 16 where tyre changes model, keep historical docs marked.
- Test counts: `305` (Phase 0-11), `322` (with Phase13), `351` (with Phase14), `372` (with Phase16) — **report accurately per workstream R**, not single number.

## Required Actions

1. Fix RNG to Level A (driver/constructor exact, lap noise documented Level B with tolerance)
2. Audit tyre coverage with actual counts (not assumed)
3. Re-run calibration from current dataset and verify no leakage
4. Update manifests with honest version lineage (do not bump dataset if no data change)
5. Create missingness semantics taxonomy and test
6. Performance regression with <30s target
7. Final audit report

**Risk:** RNG diff 0.196 is the highest scientific risk — must be root-caused, not tolerance-loosened.
