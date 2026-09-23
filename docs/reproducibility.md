# Reproducibility Contract

> What "reproducible" means in this repository — exactly, and what it does
> not mean. If a claim below cannot be verified, the honest label
> (`NOT_VERIFIED`) applies instead.

## 1. Definitions

A simulation run is identified by:

| Element | Example | Where recorded |
| --- | --- | --- |
| Master seed | `42` | request + result |
| Simulation count | `N=1000` | request + result |
| Component RNG streams | weather / race-control / strategy / AR1 / reliability | `RandomProvider.get_stream(name)` |
| Scenario | interventions + content hash | `scenario_content_hash` |
| Scenario fingerprint | baseline + versions | `baseline_fingerprint` |
| Dataset version + hash | `f1-dataset-v1.3` / `2cce529c` | provenance |
| Calibration version | `calibration-v1.0.0` (+ artefact hashes) | provenance |
| Engine / model / simulation | `raceengine-v2.2.0` / `0.9.0` / `9.2.0` | provenance |
| Enabled modules | strategy/setup/weather/race-control flags | provenance config |
| Environment hash seed | `PYTHONHASHSEED` | **not** in output — operator responsibility |

Reproducibility levels:

- **EXACT** — same backend code + same environment (Python/NumPy versions)
  + same inputs + same `PYTHONHASHSEED` ⇒ bit-identical outputs
  (verified: repeated in-process calls identical; `PYTHONHASHSEED=0`
  cross-process calls identical).
- **NUMERICALLY EQUIVALENT** — different numerical backend or BLAS build
  within Monte Carlo tolerance (distributions agree within sampling error).
- **STATISTICALLY COMPATIBLE** — different N or seed: distributions
  comparable, individual draws not identical.
- **NOT GUARANTEED** — different `PYTHONHASHSEED` (see §3), different model
  versions, or synthetic-vs-historical driver sets (see §4).

Cross-platform byte-level identity is **NOT_VERIFIED** and is not claimed.

## 2. RNG design

`RandomProvider(seed)` owns one NumPy `Generator`; `get_stream(name)`
derives an independent per-component generator so disabling weather (for
example) cannot shift the race-control stream. Monte Carlo uses CRN:
simulation `i` derives from `seed + i·offset` (reference) or global-index
RNG (vectorized/chunked — order- and worker-independent, tested by
`test_phase31_chunking.py`).

## 3. Known limitation: salted-hash stream derivation (audit A7)

`get_stream()` derives stream seeds via Python's builtin `hash()`, which is
salted per OS process. Consequence: **identical inputs in two processes with
different `PYTHONHASHSEED` produce different streams and different results.**
Same-process repeats are bit-identical (tested). Mitigations in force:

- CI, docs, and examples set **`PYTHONHASHSEED=0`** (verified bit-identical
  across processes under this setting).
- The principled fix (stable `hashlib` derivation + re-baseline + version
  bump) is specified in the audit but intentionally **not** applied in
  Phase 33: it changes every stream seed and therefore every output, which
  is a scientific behaviour change requiring owner approval.

`race_engine.py:1315` (`hash(driver_id) % 1000`) and `weekend.py:62` share
the pattern and the same constraint.

## 4. Dataset-availability caveat

When canonical data is absent, services degrade honestly: the single-race
and Monte Carlo paths build **synthetic drivers** (`driver_00…19`,
deterministic skills from IDs) on real calendar tracks, and race listing
uses a 6-track fallback calendar. Therefore the same `race_id` + seed can
yield different driver sets (and different results) across environments.
Every result's provenance states the dataset version; the reproducible
example (`docs/examples/reproducible_bahrain.md`) records which driver set
it used. Missing inputs are never silently substituted — fallbacks are
labelled synthetic.

## 5. How to reproduce a result

1. Note `race_id`, `seed`, `N`, module flags, and versions from the result's
   `provenance` / `reproducibility` block.
2. Set `PYTHONHASHSEED=0`, same code revision, same dataset state
   (`python backend/scripts/verify_dataset.py`).
3. Re-run the same endpoint/service call. Expected: EXACT (same process
   family) or bit-identical under fixed hash seed.
4. Compare `win_probabilities` / classification hashes and the fingerprint.

## 6. Test coverage for this contract

- `@pytest.mark.reproducibility`: `test_phase16_6_reproducibility.py`,
  `performance/test_phase15_performance.py` (determinism, RNG streams,
  reference-vs-optimized equivalence, fingerprints).
- `@pytest.mark.leakage`: `test_phase22_leakage.py` (+ validation probes).
- Chunk/order/worker independence: `test_phase31_chunking.py`.
- Version pins: `test_versions_unchanged`, `test_production_versions_unchanged`.
