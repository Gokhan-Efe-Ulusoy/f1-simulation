# Dependencies

> No upgrades or removals were performed in Phase 33. This is a report, not
> a change. Frontend `package-lock.json` and backend `pyproject.toml` pin
> what CI installs.

## Backend production (`pyproject.toml [project.dependencies]`)

| Package | Used by (verified) |
| --- | --- |
| fastapi ≥0.110 | `app/api/*`, `app/main.py` |
| uvicorn `[standard]` ≥0.29 | server entrypoint, Docker CMD |
| pydantic ≥2.7, pydantic-settings ≥2.3 | schemas, domain models, `core/settings.py` |
| numpy ≥1.26 | RNG (`RandomProvider`, `BatchRNG`), kernels, MC aggregation |
| scipy ≥1.13 | calibration/statistics paths |
| pandas ≥2.2 | data pipelines, calibration marts |
| sqlalchemy ≥2.0 | `core/database.py`, job persistence models |
| asyncpg ≥0.29 | async Postgres driver |
| python-dotenv ≥1.0 | `.env` loading via pydantic-settings |

All nine are imported by production code. None flagged for removal.

## Backend dev (`[project.optional-dependencies] dev`)

pytest / pytest-asyncio / pytest-cov (suite), ruff (lint — CI
informational), mypy (pre-existing errors documented, not gated),
pre-commit (hooks config at root + backend + frontend).

## Backend performance extra

numba, psutil — used by performance kernels/benchmarks. Optional install:
`pip install -e ".[performance]"`.

## Optional data sources (graceful fallback, verified)

- **FastF1** (not in requirements): `app/data/sources/fastf1_adapter.py`
  guards with `fastf1_available()`; absence logs
  `FastF1 load failed …` and continues. No test requires it.
  (The `test_batch_invariance` log line mentioning FastF1 is this notice,
  not the failure cause — see audit A3.)

## Frontend (`frontend/package.json`)

Runtime: next 14.2, react/react-dom 18, axios 1.7 (API client), clsx +
tailwind-merge (styling), recharts (charts). Dev: jest + ts-jest +
jest-environment-jsdom + testing-library, typescript 5.5, eslint +
eslint-config-next, prettier (+tailwind plugin), tailwindcss + autoprefixer.
All wired to npm scripts (`dev/build/start/lint/type-check/test`).

## Scripts / acquisition helpers

Phase scripts import `requests`-style fetching inline or via stdlib plus the
backend packages above; sidecar hashing uses stdlib `hashlib`
(`app/data/external/checksums.py`). No new dependency is needed for
`verify_dataset.py` (stdlib only).

## Notes for contributors

- Do not add a dependency to "make the project look complete".
- Optional dependencies must degrade with a clear message (FastF1 pattern).
- CI installs `.[dev]` (backend) and `npm ci` (frontend); anything else
  must be documented here first.
