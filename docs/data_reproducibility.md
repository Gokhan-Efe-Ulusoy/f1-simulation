# Data Reproducibility

> What is committed, what is ignored, and how another developer reconstructs
> the dataset. No step here downloads anything silently; acquisition scripts
> record sidecars and quarantine failures.

## 1. Committed vs ignored

**Committed** (reproducibility-relevant, small):

- `backend/data/manifests/` — dataset registry, acquisition/canonical/
  calibration manifests, checkpoints, source catalog (≈40 files).
- `backend/data/derived/` — `constructor_features.json`,
  `decomposition.json`, `scenarios_sample.json` (+ `.gitkeep` placeholders).
- `backend/data/calibration/` — fitted models, diagnostics, backtests,
  phase marts (≈80 JSON/parquet, largest `lap_mart.parquet` ≈ 8 MB).
- `backend/data/validation/` — coverage/quality/reconciliation reports.
- `backend/data/regulations/`, `licensing.json`, `README.md`,
  `calibration_candidates/`.

**Ignored** (large / re-derivable / environment-local):

- `backend/data/raw/` (≈14,461 files locally) — provider payloads.
- `backend/data/canonical/` (≈2,414 files) — resolved records.
- `backend/data/external_staging/`, `backend/data/simulation/`
  (benchmarks/experiments), `backend/data/simulations.db`,
  `data_backup_*/`.

A fresh clone therefore contains **0 canonical/raw files** — most phase
tests and the historical API paths require a local dataset. This is by
design (no massive dumps in git) and is stated wherever it matters,
including CI (which runs only data-free suites without a dataset).

## 2. Acquisition (raw)

Phase scripts under `backend/scripts/` (see audit appendix for the index):

- `phase12_acquisition/master/finalize`, `phase22_5_acquisition`,
  `phase22_6_acquisition`, `phase22_7_acquire_fast/acquire_laps/acquisition`
  fetch provider data with retries, checkpoints, and rate limits.
- Every raw file gets `.sha256` + `.provenance.json` sidecars
  (`app/data/external/checksums.py`); mismatches quarantine instead of
  overwriting; 9 files quarantined in the v1.3 cycle, 0 failed.
- External APIs are **not** required for normal CI or for the reproducible
  example.

## 3. Canonicalization

- `phase22_6_canonicalize.py`, `phase22_7_canonicalize.py` (+
  `phase22_7_preflight.py` gates) resolve entities to stable IDs and write
  `races.json` / `results.json` / laps / pit-stop families.
- `phase22_7_finalize.py` freezes `f1-dataset-v1.3`: row counts
  (1,172 races · 26,228 results · 552,656 laps · 12,747 pit stops),
  file hashes (`races 2cce529c`, `results 112c8475` — `sha256(bytes)[:8]`
  of the canonical JSON files), and the `UNCHANGED_FROM_V1.1` backbone
  attestation. `frozen: true`, `calibration_changed: false`,
  `simulation_behavior_changed: false`.

## 4. Verification

```bash
cd backend
python scripts/verify_dataset.py --offline   # manifests only (CI-safe)
python scripts/verify_dataset.py             # + row counts, hashes, PKs, orphans
```

The script **never repairs**: missing layers → `NOT_AVAILABLE` (exit 0);
hash mismatch / duplicate PKs / orphans / manifest inconsistency → exit 2.
Current local state: 34/34 checks pass, including byte-hash equality of the
canonical files against the frozen manifest.

## 5. Source limitations & licensing

- 2026 season rounds 15–23 `NOT_AVAILABLE` (season in progress).
- Intervals parquet partial (12/84; raw complete); telemetry bulk absent.
- Pit durations are totals; lane/stationary split `NON_IDENTIFIABLE`.
- ERA5 rows are **reanalysis, not sensors**; OpenF1 overlap classified, not
  blindly merged; Jolpica/OpenF1 lap-1 numbering offset documented.
- Fuel / setup / strategy history `NON_IDENTIFIABLE`; lap-1 systematic
  offset documented between sources.
- Terms: `backend/data/licensing.json` + `backend/docs/data-licensing.md`
  (project code license is separate — see root `LICENSE`).

## 6. Reconstructing the dataset (another developer)

1. Clone, install backend deps, copy `.env.example` → `.env`.
2. Run acquisition scripts in phase order (12 → 22.5 → 22.6 → 22.7);
   each is checkpointed and resumable; sidecars prove integrity.
3. Run canonicalization + `phase22_7_finalize.py`.
4. Run `verify_dataset.py` — hashes and counts must match the committed
   manifest, or the reconstruction diverged (report, do not force).
5. Record the new environment in your own manifest; never overwrite
   `f1-dataset-v1.3.json` (append-only registry).
