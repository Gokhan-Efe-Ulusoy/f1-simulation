# Phase 33 — Repository Audit

**Date:** 2026-09-23
**Auditor:** Phase 33 engineering pass
**Baseline:** Phase 32 stable (`2910c3f`), dataset `f1-dataset-v1.3`,
engine `raceengine-v2.2.0`, model `0.9.0`, simulation `9.2.0`
**Rule:** Nothing in this audit changes simulation mathematics. Findings are
classified A (must fix), B (should fix), C (cosmetic / future). Deletions are
proposed only where zero references exist; everything else is documented.

---

## 1. Scope inspected

- `backend/app/` (api, core, data, domain, jobs, models, repositories,
  schemas, services, simulation, utils)
- `backend/tests/` (51 test files), `backend/scripts/` (44 scripts),
  `backend/docs/` (~200 phase reports), `backend/data/` (tracked manifests,
  derived, calibration models, validation, regulations)
- `frontend/` (App Router pages, `lib/api`, 4 Jest suites)
- Root: `README.md`, `docker-compose.yml`, `.pre-commit-config.yaml`,
  `backend/Dockerfile`, `frontend/Dockerfile`, `backend/pyproject.toml`,
  `frontend/package.json`, `.env.example` files
- Verified absent: `.github/` (no CI), `LICENSE`, `CONTRIBUTING.md`,
  `SECURITY.md`, `CITATION.cff`, `CHANGELOG.md`, root `docs/` depth
  (only `docs/architecture.md` exists)

---

## 2. Findings

### A1 — Stale provenance on the CURRENT Monte Carlo path [A]

**Files:**

- `backend/app/simulation/performance/vectorized_montecarlo.py:768-781`
- `backend/app/services/montecarlo_service.py:139-145` (chunked branch)

Both emit hardcoded provenance for production Monte Carlo results:

```python
"dataset_version": "f1-dataset-v1.1",
"engine_version": "raceengine-v1.4.0",
"model_version": "0.5.0",
```

Current canonical values (per `metadata_service.py`, `version.py`,
`simulation_service.py`) are `f1-dataset-v1.3` / `raceengine-v2.2.0` /
`0.9.0`. Verified live: `run_montecarlo("2024-bahrain", N=50, seed=42)`
returns `engine_version: raceengine-v1.4.0, model_version: 0.5.0` while
`/api/v1/metadata` returns `raceengine-v2.2.0 / 0.9.0 / f1-dataset-v1.3`.
The single-race path (`simulation_service._provenance`) is correct; only the
Monte Carlo path is stale.

**Why must-fix:** the API presents stale versions as CURRENT production
provenance. This is a packaging-correctness bug, not a model change.
**Fix:** read versions from `app.simulation.version` centrally in both
places. Simulation mathematics (RNG, aggregation) untouched; no test asserts
the stale MC provenance values (verified: only `test_phase18` asserts
`0.5.0`/`v1.4.0`, and that targets the legacy `RaceControlAwareRaceEngine`,
not this path).

### A2 — Stale fallback versions in scenario fingerprinting [A]

**File:** `backend/app/simulation/scenario/compiler.py:33-49`
(`_versions()`). `version.py` defines no `DATASET_VERSION` /
`CALIBRATION_VERSION`, so `getattr` fallbacks silently yield
`f1-dataset-v1.1`, `calibration-v1.0.0`, `model 0.8.0`,
`engine raceengine-v2.1.0`, `strategy-v1.0.0` — all stale as CURRENT.
These feed `baseline_fingerprint()`, so scenario fingerprints embed stale
labels.

**Fix:** align fallbacks with canonical current values
(`f1-dataset-v1.3`, `0.9.0`, `raceengine-v2.2.0`, `strategy-v1.1.0`).
Safe: `test_phase21_scenario.py::test_fingerprint_changes_and_reproduces`
asserts only relational properties (equal / not-equal), never absolute
fingerprint values (verified by inspection).

### A3 — `test_batch_invariance` asserts a statistically unguaranteed property [A]

**File:** `backend/tests/test_phase16_6_reproducibility.py:53-72`.
The test runs legacy `RaceEngineV15` with N=10 vs N=100 (same seed) and
asserts the argmax driver is identical. With CRN/global-index RNG the first
10 draws of the N=100 run equal the N=10 run, but `win_probability`
quantisation (0.1 vs 0.01 steps) means the argmax can legitimately differ —
this is sampling noise, not a determinism property. Current status:
deterministically FAILS (`max-verstappen` vs `norris`). The
`FastF1 load failed` line in the log is an unrelated optional-dependency
notice, not the cause.

**Fix (per Phase 33 §12, option B refined):** keep the test and its name;
replace the cross-N argmax assertion with exact bit-identical determinism
assertions (N=10 twice, N=100 twice) plus a documented comment explaining why
cross-N argmax equality is not asserted. This strengthens the determinism
guarantee (exact equality, twice the coverage) instead of weakening it, and
the new assertions pass deterministically.

### A4 — No CI configuration [A]

`.github/` does not exist. There is no automated gate for backend tests,
leakage tests, frontend tests/build, lint, or manifest validation.
**Fix:** add `.github/workflows/ci.yml` (no dataset download, no network;
core suite excludes `statistical`/`optional_data` markers, with a separate
job documenting them).

### A5 — Canonical/raw data absent from a fresh clone; most tests require it [A]

`git ls-files backend/data/canonical` → **0 files**;
`backend/data/raw` → **0 files** (both correctly ignored per data policy).
But `state_builder.load_historical_race`, `race_service`, and the majority
of `backend/tests/test_phase*.py` read `data/canonical/races.json` /
`results.json` at import/test time. Consequence: a fresh clone (or CI
runner) cannot execute most backend tests. This is the largest
reproducibility risk in the repository.

**Fix (no data committed):** (1) document explicitly in
`docs/data_reproducibility.md`; (2) CI runs the subset that works without
canonical data (API fallback paths, unit, leakage, determinism core);
(3) provide `backend/scripts/verify_dataset.py` that reports
`NOT_AVAILABLE` for missing layers instead of failing opaquely;
(4) the reproducible example uses the offline-capable single-race synthetic
fallback and records which driver set was used.

### A7 — Cross-process determinism broken by salted `hash()` seed derivation [A]

**Files:**

- `backend/app/simulation/core/random.py:69`
  (`stream_seed = hash((self._seed, name)) & 0xFFFFFFFF`)
- `backend/app/simulation/weekend.py:62` (same pattern)
- `backend/app/simulation/core/race_engine.py:1315`
  (`sim_idx=hash(driver_id) % 1000`)

Python's builtin `hash()` for tuples/strings is salted per process
(`PYTHONHASHSEED`). Every `RandomProvider.get_stream()` call — i.e. every
isolated component stream (weather, race-control, strategy, AR1) — therefore
derives a **different seed in each OS process**. Verified empirically
(2026-09-23): `run_montecarlo("2024-bahrain", N=50, seed=42)` in two
processes yields different win distributions (`73e1919…` vs `41514c…`);
single-race P3/P4 swap across processes. Within one process, repeated calls
are bit-identical (verified). The existing test suite passes because each
`pytest` invocation is a single process.

**Why must-fix-grade but NOT fixed in Phase 33:** the correct repair —
stable derivation via `hashlib.sha256` — changes every stream seed and hence
every simulation output. That is a scientific behaviour change, forbidden by
Phase 33 §30 without owner approval and a full re-baseline. Per §30,
**STOP AND REPORT**: reported here, not silently implemented.

**No-code-change mitigation applied in Phase 33:**

- CI (`ci.yml`), docs, and the reproducible example set
  `PYTHONHASHSEED=0`, under which cross-process runs were verified
  bit-identical (`de519a61… == de519a61…`).
- `docs/reproducibility.md` downgrades the EXACT guarantee to
  "same backend + same environment + same `PYTHONHASHSEED`" and records this
  limitation honestly.

**Remediation proposal (future phase, owner decision required):**
replace `hash()` derivation with
`int(hashlib.sha256(f"{seed}:{name}".encode()).hexdigest()[:8], 16)`,
re-baseline all fingerprints, bump `SIMULATION_VERSION`, and record the
migration in `docs/version_lineage.md`.

### A8 — Missing open-source governance files [A]

No `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`, `CITATION.cff`,
`CHANGELOG.md`, `CODE_OF_CONDUCT.md`, PR/issue templates.
**Fix:** create all; `LICENSE` is a placeholder explicitly requiring owner
confirmation (no license is falsely claimed). External data licences stay
with `backend/data/licensing.json` + `backend/docs/data-licensing.md`.

### B1 — `settings.SIMULATION_MODEL_VERSION` drift [B]

`backend/app/core/settings.py:31` defaults `SIMULATION_MODEL_VERSION` to
`"0.1.0"` (== `APP_VERSION`, the *application* release), surfaced via
`/health` (`health.py`). Production model is `0.9.0`. No test asserts the
health value. Renaming/aligning is owner-visible API output; left unchanged
in Phase 33, documented here and in `docs/version_lineage.md`.

### B2 — `backend/.env.example` documents the drifted default [B]

`SIMULATION_MODEL_VERSION=0.1.0` mirrors B1. Left unchanged for consistency
with B1; documented.

### B3 — Root `README.md` is stale [B]

Describes a "16-phase process" (project is at Phase 32+), "planned"
endpoints that already exist, a `simulation/` top-level directory that does
not exist, and `frontend/app/features|hooks|types` that do not exist; no
mention of evidence tiers, leakage controls, dataset hashes, or current
versions. **Fix:** rewrite (Phase 33 §5).

### B4 — Duplicate `lap_time` vs `laptime` packages [B]

`app/simulation/lap_time/` (model.py, 418 lines) and
`app/simulation/laptime/` (baseline/decomposition/effects/fingerprint/…).
Both imported (`__init__.py` imports from both). No consolidation attempted
in Phase 33 (behaviour risk); documented as tech debt. Do not merge without
a dedicated equivalence gate.

### B5 — `docker-compose.yml` dev-only credentials [B]

`POSTGRES_PASSWORD: postgres` committed in plaintext. Acceptable for local
dev, but must be documented as dev-only in `SECURITY.md` with override
instructions. No secret rotation needed (no production deployment in repo).

### B6 — Undocumented scripts [B]

44 scripts in `backend/scripts/`; most are phase acquisition/benchmark
harnesses with no header docs on required data/network. Documented in
`docs/dependencies.md` + script index in the audit appendix; not deleted
(some are referenced by phase docs; all are history).

### B7 — Frontend/backend contract partly implicit [B]

`frontend/app/lib/api/types.ts` mirrors backend schemas but there is no
contract test pinning them. Phase 32 contract tests cover backend behaviour;
a types-vs-schema drift check is future work (documented, C/B borderline →
B because silent UI breakage risk).

### C1 — Historical race-engine chain `race_engine_v14..v22` [C — keep]

Nine versioned engines form an inheritance chain (v15→v14 … v22→v21) used
by: legacy regression tests (phases 14–21 assert old provenance — these
tests *pin history* and must not be touched), old benchmark scripts, and
`replay_engine.py` (imports v22) / `scenario/engine.py` (imports v21).
Classification: **LEGACY, referenced, keep**. The production engine is
`app/simulation/core/race_engine.py` (used by `simulation_service`).
No deletion proposed.

### C2 — Legacy `MonteCarloRunner` (`montecarlo.py`, engine v1.0.0) [C — keep]

Superseded by `VectorizedMonteCarlo`; still imported by old scripts only.
Provenance `v1.0.0` is *historical*, not stale-as-current. Keep, document
as LEGACY.

### C3 — Ruff E501 pre-existing warnings [C]

`ruff check` reports line-too-long in `metrics.py`, `simulate.py`, etc.
Pre-existing per Phase 32 notes; not introduced by Phase 33. Left as-is
(reformatting risks diff noise; CI runs ruff informationally).

### C4 — Mypy pre-existing errors [C]

Per Phase 32 baseline, mypy reports pre-existing errors. Phase 33 does not
claim to fix them; CI does not gate on mypy.

### C5 — `tsconfig.tsbuildinfo` tracked [C]

`frontend/tsconfig.tsbuildinfo` is committed (build artifact). Harmless
(1 line); recommend ignoring in future, not worth a history rewrite now.

---

## 3. Secrets / environment leakage scan

- Searched `backend/**` + `frontend/**` (excluding `.venv`, `node_modules`)
  for `API_KEY|SECRET_KEY|PASSWORD|TOKEN|PRIVATE KEY|BEGIN RSA|connection
  string`: **no real secrets**. Only hits: `docker-compose.yml`
  dev-only `postgres:postgres` (B5), `DATABASE_URL` defaults in
  `settings.py`/`.env.example` (localhost dev defaults, no real
  credentials), and the word "token" in dependency internals.
- `.env` files: none exist in the working tree; `.env` / `.env.*` ignored,
  `*.env.example` templates preserved.
- **Result: PASS — no secrets, no private keys, no `.env` tracked.**

## 4. Large-file / git-hygiene scan

- Files >100 MB tracked: **0**. Largest on-disk data files
  (`observations_full.json` ~16 MB, `canonical/results.json` ~15 MB,
  `lap_mart.parquet` ~8 MB) are either tracked-but-small or ignored.
- Ignored as designed: `.venv/`, `node_modules/`, `.next/`,
  `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`,
  `data_backup_*/`, `backend/data/canonical/`, `backend/data/raw/`,
  `backend/data/external_staging/`, `backend/data/simulation/`,
  `backend/data/simulations.db`.
- Tracked data (manifests, derived features, calibration models,
  validation, regulations) matches the declared data policy.

## 5. Dependency snapshot (detail in `docs/dependencies.md`)

- Production: fastapi, uvicorn, pydantic(+settings), numpy, scipy, pandas,
  sqlalchemy, asyncpg, python-dotenv. All imported by production code.
- Dev: pytest(+asyncio,+cov), ruff, mypy, pre-commit.
- Performance extra: numba, psutil.
- Optional (graceful fallback verified): `fastf1` via
  `fastf1_available()` guard — absence only logs a notice.
- Frontend: next 14.2, react 18, axios, recharts; dev: jest, ts-jest,
  testing-library, eslint, prettier, tailwind.
- No version conflicts observed; no upgrades performed in Phase 33.

## 6. Reproducibility risks (carried into docs)

1. Fresh clone lacks canonical/raw data → most phase tests need local data
   (A5; CI strategy + `verify_dataset.py` mitigate).
2. API single-race/MC fall back to synthetic drivers when canonical data is
   absent → same `race_id`+seed can yield different driver sets across
   environments (documented in `docs/reproducibility.md`; example records
   its driver set).
3. Cross-platform byte-identity never verified → contract claims EXACT only
   for same backend+environment (see `docs/reproducibility.md`).
4. Absolute fingerprint `b22a1491` pinned in `test_phase26_fuel_tyre.py:384`
   — untouched and passing; any future provenance change must re-verify it.

## Appendix — script index (all retained)

Acquisition: `phase12_acquisition/master/finalize`, `phase22_5_acquisition`,
`phase22_6_acquisition/canonicalize`, `phase22_7_acquire_fast/acquire_laps/
acquisition/canonicalize/finalize/preflight/probe/remaining`,
`phase22_7_*` docs via `phase23_docs`, `phase24_docs`, `phase25_docs`.
Calibration/model: `phase13_calibration`, `phase23_calibration`,
`phase24_circuit_model`, `phase25_tyre_calibration/join`,
`phase26_fuel_tyre_decomposition`, `phase27_decomposition`,
`create_baseline.py`. Benchmarks/profiles: `phase14_validation`,
`phase15_benchmark*`, `phase15_profile`, `phase16_benchmark/coverage`,
`phase20/21/22_benchmark`, `phase22_experiment_*`, `phase22_walkforward`.
Debug: `debug_constr`, `debug_pace`, `recovery_test`, `rng_investigation`,
`test_opt`. New in Phase 33: `verify_dataset.py` (validation only, never
repairs).
