# Phase 33 — Completion Report

```text
========================================
PHASE 33 — PRODUCTION REPOSITORY
================================

Repository:
status: audited, documented, CI-gated; 3 grouped commits on master

Git:
branch: master
commits: Phase-32 baseline (2910c3f) + Phase-33 series (packaging fixes;
  CI + verification tooling; documentation/governance)
working_tree_clean: true (verified post-commit)

Security:
secrets_found: false
private_keys_found: false
env_files_tracked: none (.env/.env.* ignored; *.env.example are placeholders)

Large Files:
over_100mb: 0 tracked (largest tracked blobs ~100 KB)
largest_files: observations_full.json ~16 MB, canonical/results.json ~15 MB,
  lap_mart.parquet ~8 MB (all within policy; raw/canonical bulk ignored)

Dataset:
version: f1-dataset-v1.3
hashes: races 2cce529c, results 112c8475, laps ac13fa1f (recomputed from
  disk by verify_dataset.py — byte-identical to frozen manifest)
content_changed: false

Production Model:
changed: false (mathematics untouched)
engine: raceengine-v2.2.0
model: 0.9.0
simulation: 9.2.0

Tests:
backend: 1059 passed, 2 skipped (pre-existing skips), 0 failed —
  unit 192 + API/leakage/repro 151 + phases 15/17-27 435 + phases 9-14/16/22.5-7 281
frontend: 13 passed (4 suites)
build: Next.js production build PASS
leakage: 5 passed (test_phase22_leakage.py)
reproducibility: 11 passed incl. corrected test_batch_invariance
dataset_validation: verify_dataset.py 34/34 full, 26/26 --offline

Optional Dependencies:
FastF1: NOT_INSTALLED (graceful fallback verified; absence only logs a
  notice; no test requires it)

CI:
status: configured (.github/workflows/ci.yml) — backend-unit gates every
  PR (data-free); backend-api runs where the local dataset exists, else
  skips explicitly; frontend tests + build always run.
  PYTHONHASHSEED=0 pinned globally (audit A7).

Documentation:
status: complete — README rewritten; docs/architecture.md (scientific
  layers); docs/reproducibility.md (contract incl. A7 limitation);
  docs/data_reproducibility.md; docs/version_lineage.md;
  docs/dependencies.md; docs/examples/reproducible_bahrain.md (recorded
  output: classification tsunoda/alonso/hamilton/ocon/leclerc, MC
  fingerprint 6b7cd5262bc7eee3); CHANGELOG.md (Phase 0–33);
  backend/docs/phase33_repository_audit.md (this report's evidence).

Provenance:
status: verified and corrected — Monte Carlo provenance + scenario
  fingerprint defaults now report current versions (audit A1/A2);
  metadata/single-race paths already correct; legacy pins untouched.

Reproducibility:
status: contract documented; within-process bit-identical (verified);
  cross-process bit-identical under PYTHONHASHSEED=0 (verified
  de519a61… == de519a61…); salted-hash derivation limitation honestly
  recorded with a specified future fix (audit A7, NOT applied — would
  change simulation outputs).

Scientific Integrity:
status: HOLDS — no fabricated data, no invented coefficients, no
  auto-promotion (calibration still v1.0.0), no weakened assertions
  (batch_invariance strengthened to exact double determinism), no fake
  endpoints, no deleted functionality.

Legacy Equivalence:
status: VERIFIED — same seed/inputs give same simulation outputs before
  vs after Phase 33 within-process (single-race classification and MC
  distributions identical apart from corrected provenance labels);
  absolute fingerprint b22a1491 (phase26) still passes; all 435
  fingerprint/provenance-sensitive phase tests green.

New Technical Debt:
blockers: none
documentation: settings SIMULATION_MODEL_VERSION naming drift (B1),
  lap_time/laptime package duplication (B4), frontend/backend contract
  pinning (B7) — all recorded in audit for future phases
limitations: canonical/raw data absent from fresh clones (A5, by design);
  pyarrow DLL transiently blocked once by Windows App Control during
  validation (re-ran clean — environmental flake, documented);
  cross-platform byte identity NOT_VERIFIED

========================================
PHASE_33_STATUS = COMPLETE_WITH_LIMITATIONS
========================================
```

Limitations are the documented, by-design ones above (data policy,
hash-seed constraint, unverified cross-platform identity) — no open
blocker. Per §34 they are stated, not hidden.

Scientific state carried forward:

```text
KEEP_PRODUCTION_MODEL
NO_AUTO_PROMOTION
NO_DATA_FABRICATION
```
