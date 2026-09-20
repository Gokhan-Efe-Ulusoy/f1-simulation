# Phase 32 — Limitations

- Non-git repository (still true; documented, no init). `.venv/node_modules/.next/__pycache__/.pytest_cache` present on disk, never committed (no VCS).
- Strategy Lab / Counterfactual / Championship / Regulation Lab / NL "what-if": NOT implemented; UI shows planned-disabled honestly.
- Single-race weather/setup remain provenance-only (Phase 29–31 limitation); Monte Carlo cap 5000; chunking/distributed infra unchanged.
- Full backend pytest suite not executed (timeout); frontend `next lint` not run (only build's built-in lint); mypy not run for Phase 32 (no backend source changes; frontend has no mypy).
- Scientific lineage unchanged: dataset f1-dataset-v1.3, all production versions, RNG streams, determinism, leakage, chunk equivalence verified by spot-checks, not re-benchmarked.
