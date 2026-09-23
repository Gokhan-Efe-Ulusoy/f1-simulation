# Scientific Architecture

> Current production: dataset `f1-dataset-v1.3` · engine `raceengine-v2.2.0`
> · model `0.9.0` · simulation `9.2.0`. Historical designs live in
> `backend/docs/phase*.md` and are preserved there, not rewritten here.

The platform is a pipeline. Data flows strictly downward; no layer reaches
upward or sideways for information it has not been given. In particular, no
decision-making layer ever sees future information (strict `as_of` policy,
enforced by tests marked `leakage`).

```text
DATA (providers: Jolpica, OpenF1, Open-Meteo/ERA5, f1db, FastF1-probe)
  ↓ acquisition + sha256 sidecars + provenance sidecars
RAW DATA (byte-identical payloads, ignored by git)
  ↓ normalisation (source-flavoured common shape)
NORMALIZED
  ↓ entity resolution + validation (stable IDs, no orphans)
CANONICAL DATA (races / results / laps / pit stops / …)
  ↓ calibration (fitters with uncertainty + method, NO auto-promotion)
CALIBRATION (priors, posteriors, promotion gates — mostly PRIOR_ONLY)
  ↓
DOMAIN MODELS (Driver / Car+Engine / Track / Team — Pydantic-validated)
  ↓───────────┬───────────┬──────────────┬───────────┬───────────
TYRE        WEATHER    RACE CONTROL    STRATEGY     SETUP
tyre-v1     weather-   racecontrol-    strategy-    setup-
(unfitted,  v1 (+calib  v1 (+policy    v1.1 (+pit   v1
 NON_IDENT   v1, PRIOR_  v1, PRIOR_     loss chan,
 for hist.)  ONLY)       ONLY)          PRIOR_ONLY) (PRIOR_ONLY)
  ↓───────────┴───────────┴──────────────┴───────────┴───────────
SCENARIO (validated spec → compiled interventions, fingerprinted)
  ↓
COUNTERFACTUAL (baseline vs intervened, same seed — ceteris paribus)
  ↓
RACE ENGINE (raceengine-v2.2.0 — event-sourced lap loop, 2000+ lines)
  ↓ single race                      ↓ Monte Carlo (vectorized, chunked)
RESULTS + EXPLANATION / PROVENANCE (versions, seed, hashes, evidence tiers)
```

Per-layer contract:

## 1. DATA / RAW

- **Purpose:** byte-identical provider payloads with integrity proof.
- **Inputs:** provider APIs / local dumps (Jolpica bulk, OpenF1 live timing,
  Open-Meteo ERA5 reanalysis, f1db snapshots, FastF1 probe cache).
- **Outputs:** `data/raw/<source>/…` + `.sha256` + `.provenance.json`
  sidecars per file.
- **Evidence tier:** N/A (observations, not estimates).
- **Randomness:** none. **Leakage rules:** retrieval timestamps recorded;
  quarantine on failure (9 files quarantined in v1.3 acquisition).
- **Performance:** ~14k files locally; never committed, never downloaded
  in CI. **Dependencies:** `app/data/sources/*`, `app/data/external/*`.
- **Legal:** provider terms preserved — see `backend/data/licensing.json`.

## 2. CANONICAL DATA

- **Purpose:** entity-resolved, validated records with stable IDs.
- **Inputs:** normalized source records. **Outputs:** `races.json` (1,172),
  `results.json` (26,228), laps/pit-stop families, `qualifying.json`.
- **Evidence tier:** observations (`LIMITED` where coverage is partial —
  e.g. intervals parquet 12/84, telemetry bulk absent).
- **Randomness:** none. **Leakage rules:** every record carries dates;
  consumers filter `as_of < race_date` (strict-before).
- **Performance:** ~2.4k parquet partitions + JSON; git-ignored, hashed in
  manifests (`races 2cce529c`, `results 112c8475`).
- **Dependencies:** `app/data/models/canonical.py`, `pipeline.py`,
  `resolution.py`, `validation.py`.

## 3. CALIBRATION

- **Purpose:** fit parameters with uncertainty and method — or explicitly
  decline to (`NON_IDENTIFIABLE` / `PRIOR_ONLY`).
- **Inputs:** canonical data + calibration mart (phase23 parquet marts).
- **Outputs:** `data/calibration/models/*.json` (driver, constructor,
  circuit, era, tyre, weather, reliability…), diagnostics, walk-forward
  reports. **Promotion gates** (`promotion_gates.json`) block silent
  promotion: production calibration is still `calibration-v1.0.0`.
- **Evidence tier:** mostly `PRIOR_ONLY`/`LIMITED`; driver/circuit/
  constructor `LIMITED`.
- **Randomness:** fitters use fixed seeds; reports record them.
- **Leakage rules:** walk-forward windows only; leakage reports per phase.
- **Dependencies:** `app/data/calibration/*`, `scripts/phase23_calibration.py`
  and successors.

## 4. DOMAIN MODELS

- **Purpose:** typed, validated entities (Driver skills 0–100, Car/Engine
  specs, Track geometry/sectors, Team).
- **Inputs:** calibration + canonical identities.
- **Outputs:** Pydantic objects consumed by every downstream layer.
- **Evidence tier:** inherits per-field tiers. **Randomness:** none
  (deterministic skill derivation from IDs for synthetic fallback).
- **Dependencies:** `app/simulation/models/*`.

## 5. TYRE (`tyre/`, model `tyre-v1`)

- **Purpose:** compound physics, degradation kernels, stint modelling,
  era handling.
- **Inputs:** compound, age, track abrasion, temperature.
- **Outputs:** grip delta → lap-time effect.
- **Evidence tier:** modern `LIMITED`; **historical per-lap detail
  `NON_IDENTIFIABLE`** (no lap-granular historical tyre observations).
- **Randomness:** via engine streams only. **Leakage:** no future wear.
- **Dependencies:** `tyre/engine.py`, `kernels.py`, `model.py`.

## 6. WEATHER (`weather/`, `weather-v1` + `weather-calibration-v1`)

- **Purpose:** regime classification, transitions, AR-persistent wetness,
  forecast uncertainty.
- **Inputs:** ERA5 reanalysis (labelled as such — not sensors) + OpenF1
  weather.
- **Outputs:** per-lap wetness/rainfall trajectories shared across drivers.
- **Evidence tier:** `PRIOR_ONLY`. **Randomness:** dedicated weather stream.
- **Dependencies:** `weather/engine.py`, `transition.py`, `forecast.py`.

## 7. RACE CONTROL (`race_control/`, `racecontrol-v1` + policy `v1`)

- **Purpose:** SC/VSC/red-flag state machine, neutralisation propagation,
  restart models.
- **Inputs:** incident stream + policy table (`NEUTRALISATION_TABLE`,
  `PRIOR_ONLY`).
- **Outputs:** phase/sector trajectories, neutralised lap deltas.
- **Evidence tier:** `PRIOR_ONLY`. **Randomness:** dedicated RC stream.
- **Dependencies:** `race_control/engine.py`, `state_machine.py`.

## 8. STRATEGY (`strategy/`, `strategy-v1.1`)

- **Purpose:** pit-window, fuel, opponent-model, team-orders, live advisor;
  v1.1 adds the deterministic per-stop `pit_loss_seconds` channel
  (default 0 reproduces legacy behaviour exactly).
- **Evidence tier:** `PRIOR_ONLY`. **Randomness:** dedicated strategy
  stream. **Leakage:** future results rejected at validation
  (`future_result` probes are inert — tested).
- **Dependencies:** `strategy/engine.py`, `decision_engine.py`, `fuel.py`.

## 9. SETUP (`setup/`, `setup-v1`)

- **Purpose:** parametric offsets (ride height, wing…) with fingerprints.
- **Evidence tier:** `PRIOR_ONLY`. **Randomness:** none (deterministic
  offsets). Fingerprint changes ⇒ outcome may change (tested).

## 10. SCENARIO (`scenario/`, `scenario-v1`)

- **Purpose:** typed interventions (`family/op/target/parameter`) compiled
  against a validated spec; content hash + versioned baseline fingerprint.
- **Inputs:** baseline scenario + `ScenarioSpec`. **Outputs:** compiled
  scenario, `baseline_fingerprint`, `counterfactual_fingerprint`.
- **Randomness:** none at compile time. **Leakage:** spec validation
  rejects future-referencing parameters.
- **Dependencies:** `scenario/compiler.py`, `validation.py`, `engine.py`.

## 11. COUNTERFACTUAL / REPLAY (`replay-v1`, `counterfactual-v1`)

- **Purpose:** baseline-vs-intervened comparison under the **same seed**
  (ceteris paribus); historical replay with checkpoints, sensitivity,
  sanity gates.
- **Inputs:** scenario + seed + N. **Outputs:** experiment records with
  fingerprints, artifacts, attribution.
- **Dependencies:** `replay/*`, `race_engine_v22.ReplayAwareRaceEngine`.

## 12. RACE ENGINE (`core/race_engine.py`, `raceengine-v2.2.0`)

- **Purpose:** the production event-sourced lap loop (battle, DRS trains,
  dirty air, defence, starts, restarts, red flags, telemetry sampling).
- **Inputs:** drivers/cars/track + config + master seed.
- **Outputs:** classification, lap summary, events, provenance.
- **Evidence tier:** composed from layers above. **Randomness:** all via
  `RandomProvider` isolated streams (+ `BatchRNG` in vectorized paths).
  **Known limitation:** stream seeds derive from salted builtin `hash()` —
  set `PYTHONHASHSEED=0` for cross-process identity (audit A7).
- **Performance:** single race ≈ seconds; vectorized MC 10–20× reference.
- **History:** `race_engine_v14..v22` are LEGACY inheritance snapshots kept
  for regression tests — not the production path.

## 13. MONTE CARLO (`performance/vectorized_montecarlo.py`, chunked)

- **Purpose:** distributions (win/podium/finish/points/DNF + CI95),
  constructor aggregation, exact-integer chunked execution
  (`chunked_montecarlo.py`: global-index RNG ⇒ order/worker-independent).
- **Inputs:** calibration state + scenario + seed + N (+ chunk size).
- **Outputs:** probability tables + provenance (dataset/engine/model
  versions — corrected to current in Phase 33) + chunk manifest.
- **Randomness:** CRN per simulation index. **Leakage:** same as engine.

## 14. RESULTS / EXPLANATION / PROVENANCE

- Every externally visible result carries: dataset + dataset hash,
  calibration (+ hash where computed), engine/model/simulation versions,
  enabled modules, seed, scenario fingerprint, evidence tiers, warnings.
- Served via `services/*` (`simulation_service`, `montecarlo_service`,
  `replay_service`, `scenario_service`, `metadata_service`,
  `result_normalization`) → FastAPI `api/v1/*` → documented schemas →
  frontend `lib/api/types.ts`.

## Cross-cutting: API / jobs / frontend

- **API** (`app/api/v1`): thin validated wrappers; small jobs synchronous,
  large Monte Carlo via async queue (`app/jobs`: lifecycle, idempotency,
  priority, heartbeat, timeout, retry, cancellation, Redis-or-inprocess).
- **Frontend** (`frontend/`): Next.js 14 pages (`/`, `/simulator`,
  `/monte-carlo`, `/championship`, `/strategy`) + `EvidenceBadge`,
  `SimulationProvenance`, `JobProgress`, `ErrorState` components. Talks to
  the backend only through `lib/api/*` typed clients — no internal imports.
