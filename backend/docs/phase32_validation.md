# Phase 32 — Validation

- Backend: `tests/test_phase32_contract.py` 12/12 (valid/invalid race/seed/laps/N, async submit, polling, completed, 404, duplicate hash, scenario valid, leakage 422). Regression: `test_random_provider` + `test_phase22_leakage` 12/12; determinism spot-check same seed+race → identical classification; versions 0.9.0/f1-dataset-v1.3 unchanged.
- Frontend: 13/13 (HomePage 2, apiClient 4, simulator 4, evidence 3). `tsc --noEmit` clean, `next build` 8/8 static pages.
- Full backend suite not run (timeout); reported honestly — targeted Phase 32 + representative regression only.
