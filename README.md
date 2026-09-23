# F1 Simulation Platform

A modular, deterministic, reproducible, data-driven Formula 1 simulation
platform. Not a game and not a random result generator: every simulation
records its dataset, model versions, seed, and provenance, and every
unavailable input is reported as such instead of being invented.

## What it is

- **Race simulation** — full-race engine with pit stops, tyre degradation,
  fuel effects, overtaking, incidents, and mechanical failures.
- **Monte Carlo analysis** — vectorized engine (10–20× faster than the
  reference loop) with chunked, order-independent distributed execution.
- **Deterministic replay** — historical races re-simulated from canonical
  data with strict as-of (no future information) guarantees.
- **Counterfactuals & scenarios** — typed interventions (setup, strategy,
  weather, race-control) compiled against a validated scenario model.
- **Strategy / setup / weather / race-control modules** — each versioned,
  each carrying an explicit evidence tier.
- **Provenance & evidence tiers** — every result identifies its dataset,
  hashes, versions, seed, and scenario fingerprint.

## Example questions the system can answer

- "How would the 2024 Bahrain race distribution change if the driver had a
  different setup?"
- "What happens if a pit stop occurs five laps earlier?"
- "How does increased rainfall change race outcomes?"
- "What if a future regulation changes front-wing characteristics?"
- "How would the same race unfold under a different strategy?"

These are capabilities and usage examples, **not** claims that every
historical variable is fully calibrated. See
[Scientific integrity](#scientific-integrity) and `docs/` limitations.

## Scientific integrity

The platform never fabricates unavailable historical information. Every
model input and output carries one of these evidence tiers:

| Tier | Meaning |
| --- | --- |
| `CALIBRATED` | Fitted against observed data with validation |
| `LIMITED` | Partial evidence; use with stated uncertainty |
| `PRIOR_ONLY` | Prior/assumption only; not fitted to history |
| `PROXY_ONLY` | Indirect proxy, not the quantity itself |
| `NON_IDENTIFIABLE` | Cannot be identified from available data |
| `NOT_AVAILABLE` | Data does not exist in the dataset |

Current production tiers include: fuel `NON_IDENTIFIABLE`, historical tyre
detail `NON_IDENTIFIABLE`, strategy/setup/weather/race-control
`PRIOR_ONLY`, driver/circuit/constructor `LIMITED`. A contributor **cannot
simply tune coefficients until the simulation looks realistic** — see
`CONTRIBUTING.md`.

## Reproducibility

- One master seed fans out into **isolated RNG streams** (weather,
  race-control, strategy, AR1 lap noise, reliability) via `RandomProvider`.
- Same race + same config + same seed + same model version ⇒ identical
  output **within the same backend and environment** (set `PYTHONHASHSEED=0`
  for bit-identical results across OS processes — see
  `docs/reproducibility.md` for why).
- Every result carries **fingerprints**, **dataset hashes**, **calibration
  hashes**, and full **provenance**.
- Leakage controls: strict `as_of` policy, future-field rejection, and a
  dedicated leakage test suite (`@pytest.mark.leakage`).

## Current baseline

| Component | Version |
| --- | --- |
| Dataset | `f1-dataset-v1.3` (552,656 laps · 1,172 races · 12,747 pit stops) |
| Dataset hashes | races `2cce529c` · results `112c8475` · laps `ac13fa1f` |
| Engine | `raceengine-v2.2.0` |
| Model | `0.9.0` |
| Simulation | `9.2.0` |

Full lineage: `docs/version_lineage.md`. Verification:
`backend/scripts/verify_dataset.py`.

## Repository layout

```text
├── README.md / CONTRIBUTING.md / SECURITY.md / CHANGELOG.md / CITATION.cff
├── docker-compose.yml            # local dev stack (Postgres + backend + frontend)
├── backend/
│   ├── app/                      # FastAPI API + services + simulation engine
│   │   ├── api/                  # REST endpoints (v1)
│   │   ├── services/             # execution, simulation, montecarlo, jobs, metadata
│   │   ├── simulation/           # production engine (core/) + domain modules
│   │   │                         # (race_engine_v14..v22 are LEGACY, kept for regression)
│   │   ├── data/                 # acquisition / canonical / calibration code
│   │   └── jobs/                 # async job queue + workers
│   ├── tests/                    # unit / integration / scientific / leakage /
│   │                              # reproducibility / performance / regression
│   ├── scripts/                  # acquisition, calibration, benchmarks, verify_dataset.py
│   ├── docs/                     # phase reports + phase33 audit/completion report
│   └── data/                     # manifests, derived, calibration models, validation
│                                  # (raw + canonical parquet intentionally NOT committed)
├── frontend/                     # Next.js 14 App Router UI
├── docs/                         # architecture, reproducibility, data, versions, examples
└── .github/workflows/ci.yml      # backend unit + API (with data) + frontend
```

## Quick start

Prerequisites: Python 3.12+, Node.js 20+, Docker (optional, for Postgres).

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows  (.venv/bin/activate on POSIX)
pip install -e ".[dev]"
cp .env.example .env
$env:PYTHONHASHSEED = "0"         # required for cross-process reproducibility
pytest tests/test_health.py tests/test_car.py -q   # data-free smoke tests
python scripts/verify_dataset.py --offline          # manifest check (no download)

# A first deterministic simulation (works offline; synthetic drivers when
# canonical data is absent — see docs/examples/reproducible_bahrain.md)
python -c "from app.services.simulation_service import simulate_single_race;
print(simulate_single_race('2024-bahrain', seed=42, laps_override=5)['provenance'])"

# Frontend
cd frontend
npm ci
npm test -- --ci
npm run build
npm run dev                       # http://localhost:3000
```

Full workflow (install → configure → test → simulate → scenario → inspect):
`docs/examples/reproducible_bahrain.md`. API surface: `docs/` + OpenAPI at
`http://localhost:8000/docs` when the backend runs.

## Testing

```bash
cd backend
pytest tests/test_health.py tests/test_car.py -q          # fast, data-free
pytest tests/test_phase22_leakage.py -q                   # leakage (needs dataset)
pytest tests/test_phase16_6_reproducibility.py -q         # determinism (needs dataset)
pytest tests/test_phase28_api.py tests/test_phase32_contract.py -q  # API (needs dataset)
python scripts/verify_dataset.py                          # dataset integrity
```

Markers: `unit integration scientific leakage reproducibility performance
regression data_integrity statistical optional_data`
(e.g. `pytest -m "not performance and not optional_data"`).
Details: `docs/` + `backend/docs/phase33_repository_audit.md`.

## Data

Raw provider payloads and large canonical parquet files are **not committed**
(14k+ raw files locally). Committed: manifests, schemas, derived features,
calibration models, validation reports, regulations, lightweight fixtures.
Reconstruct the full dataset locally with the phase acquisition scripts;
validate with `verify_dataset.py`. Full policy:
`docs/data_reproducibility.md`.

## Limitations (honest summary)

- Fuel, historical tyre detail: `NON_IDENTIFIABLE`.
- Strategy/setup/weather/race-control effects: `PRIOR_ONLY` priors.
- Cross-platform byte-identity not verified; EXACT reproducibility is
  same-backend + same-environment (+ `PYTHONHASHSEED=0` across processes).
- 2026 season in progress; ERA5 rows are reanalysis, not sensors; pit
  durations are totals (lane/stationary split unavailable).
- See `backend/docs/phase32_limitations.md` and per-phase limitation docs.

## License / citation

Code license: **TBD — owner decision required** (see `LICENSE`; no license
is claimed until then). External data sources keep their own terms — see
`backend/data/licensing.json` and `backend/docs/data-licensing.md`.
If you use this project in research, see `CITATION.cff`.
