# Changelog

> Milestone-level history reconstructed from `backend/docs/phase*` reports.
> No detail invented: entries cite what the phase reports document. Version
> columns distinguish dataset / engine / model / simulation lines
> (`docs/version_lineage.md` is normative for current values).

| Phase(s) | Milestone | Dataset | Engine | Model | Simulation |
| --- | --- | --- | --- | --- | --- |
| 0–6 | Architecture, domain models, lap-time model, full race engine, tyres/fuel/pit stops, strategy engine | — | pre-v1 | pre-0.3 | pre-8 |
| 7–8 | Environment/weather racing, race resolution (overtaking, incidents, safety car) | — | pre-v1 | pre-0.3 | pre-8 |
| 9 | Historical data backbone (schema, ingestion, normalisation, eras, bridge, CLI) | f1-dataset-v0.1.0 → v1.0 | — | 0.2.0 | — |
| 10–11 | Historical dataset assembly; calibration validation readiness | f1-dataset-v1.0/v1.1 | — | — | — |
| 12 | Master acquisition pipeline (Jolpica/OpenF1/FastF1/GitHub/Kaggle/FIA/weather) | v1.1 backbone stats | — | — | — |
| 13–14 | Calibration framework; race-engine validation (`raceengine-v1.0.0`, reference) | f1-dataset-v1.1 | v1.0.0 | — | — |
| 15 | Performance: vectorized Monte Carlo (10–20×), CRN, AR1 streams | v1.1 | v1.0.0→v1.1.0 (v15) | — | — |
| 16 | Tyre model (`tyre-v1`, `0.3.0`); RNG/determinism audit (16.6) | v1.1 | v1.1.0→v1.2.0 | 0.3.0 | — |
| 17 | Weather model (`weather-v1`, `0.4.0`) | v1.1 | v1.2.0→v1.3.0 | 0.4.0 | — |
| 18 | Race-control model (`racecontrol-v1`, `0.5.0`) | v1.1 | v1.3.0→v1.4.0 | 0.5.0 | 8.4.0 |
| 19 | Strategy engine (`strategy-v1`, `0.6.0`) | v1.1 | v1.4.0→v1.5.0 | 0.6.0 | 8.5.0 |
| 20 | Setup model (`setup-v1`, `0.7.0`) | v1.1 | v1.5.0→v2.0.0 | 0.7.0 | — |
| 21 | Scenario/counterfactual model (`scenario-v1`, `0.8.0`) | v1.1 | v2.0.0→v2.1.0 | 0.8.0 | 9.1.0 |
| 22–22.7 | Historical replay, leakage controls, sensitivity; dataset freeze | **f1-dataset-v1.3** (1,172 races · 552,656 laps · 12,747 pit stops) | v2.1.0→**v2.2.0** | **0.9.0** (pit-loss) | **9.2.0** |
| 23–27 | Calibration marts, circuit/era/driver/constructor models, tyre join, fuel-tyre decomposition, lap-time decomposition | v1.3 (frozen) | v2.2.0 | 0.9.0 | 9.2.0 |
| 28 | Production REST API (FastAPI), contract tests | v1.3 | v2.2.0 | 0.9.0 | 9.2.0 |
| 29 | Execution services (deterministic, persisted, hashed) | v1.3 | v2.2.0 | 0.9.0 | 9.2.0 |
| 30 | Async job system (lifecycle, idempotency, retry, cancellation) | v1.3 | v2.2.0 | 0.9.0 | 9.2.0 |
| 31 | Chunked/order-independent Monte Carlo, priority, heartbeat, Redis-or-inprocess | v1.3 | v2.2.0 | 0.9.0 | 9.2.0 |
| 32 | Product architecture, API↔frontend contract, simulator UX, provenance/evidence UI | v1.3 | v2.2.0 | 0.9.0 | 9.2.0 |
| 33 | Production repository & open-source engineering: audit, CI, docs, provenance-label corrections (no maths change), determinism-test correction, `PYTHONHASHSEED=0` policy | v1.3 (unchanged) | v2.2.0 (unchanged) | 0.9.0 (unchanged) | 9.2.0 (unchanged) |

Notes:

- "Unchanged" in Phase 33 means simulation mathematics and dataset
  contents. Phase 33 did correct three stale version *labels* in Monte
  Carlo provenance and scenario fingerprint defaults (audit A1/A2) and
  revised one statistically unsound test assertion (audit A3) — all
  documented in `backend/docs/phase33_repository_audit.md`.
- Calibration remains `calibration-v1.0.0`: no auto-promotion at any phase
  (promotion gates enforced).
