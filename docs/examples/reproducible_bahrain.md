# Example: Reproducible 2024 Bahrain (small-N, offline, fixed seed)

> Runs without network and without downloads. Needs only the committed
> code (+ the local historical dataset for the *historical* driver set;
> without it the same commands run on synthetic drivers — see §4).
> Recorded 2026-09-23, `PYTHONHASHSEED=0`, backend revision Phase 33.

## 1. Configuration

```python
from app.services.simulation_service import simulate_single_race
from app.services.montecarlo_service import run_montecarlo

# Single race: 5 laps (short demo), all else default
r = simulate_single_race("2024-bahrain", seed=42, laps_override=5)

# Monte Carlo: N=100 (CI-sized; production uses N=1000+)
m = run_montecarlo("2024-bahrain", simulations=100, seed=42)
```

| Item | Value |
| --- | --- |
| race | `2024-bahrain` (Sakhir; calendar fallback if canonical absent) |
| seed | `42` |
| single-race laps | `5` (override; full distance otherwise) |
| Monte Carlo N | `100` |
| module flags | strategy off, setup off, weather on, race-control off (single) |
| dataset | `f1-dataset-v1.3` (hashes races `2cce529c`, results `112c8475`) |
| model / engine / simulation | `0.9.0` / `raceengine-v2.2.0` / `9.2.0` |
| calibration | `calibration-v1.0.0` (no auto-promotion) |
| environment | `PYTHONHASHSEED=0` (required — see `docs/reproducibility.md` §3) |

## 2. Recorded result summary (historical driver set)

Single race classification (20 drivers, top 5):

```text
1. tsunoda  2. alonso  3. hamilton  4. ocon  5. leclerc
```

Monte Carlo top 5 win probabilities (N=100, seed=42):

```text
alonso 0.12 · sargeant 0.10 · ocon 0.07 · albon 0.06 · gasly 0.06
```

Result fingerprint (sha256 of sorted win-probability map, first 16 hex):

```text
6b7cd5262bc7eee3
```

The single-race provenance block additionally records config version,
enabled modules, and per-domain evidence tiers
(fuel `NON_IDENTIFIABLE`, strategy/setup/weather/race-control
`PRIOR_ONLY`, driver/circuit `LIMITED`).

## 3. Reproduce it

```bash
cd backend
$env:PYTHONHASHSEED = "0"      # Windows PowerShell (export on POSIX)
python scripts/verify_dataset.py --offline
python -c "
from app.services.simulation_service import simulate_single_race
from app.services.montecarlo_service import run_montecarlo
import json, hashlib
r = simulate_single_race('2024-bahrain', seed=42, laps_override=5)
m = run_montecarlo('2024-bahrain', simulations=100, seed=42)
print([(c['driver_id'], c['position']) for c in r['classification']][:5])
print(hashlib.sha256(json.dumps(m['win_probabilities'], sort_keys=True).encode()).hexdigest()[:16])
"
```

Expected with the historical dataset present: the classification and
`6b7cd5262bc7eee3` above, bit-identical. Expected `provenance` versions:
dataset `f1-dataset-v1.3`, engine `raceengine-v2.2.0`, model `0.9.0`.

## 4. Honest caveats (read before citing numbers)

- **Driver set depends on data availability.** With `data/canonical/`
  present you get historical 2024 drivers (as above); without it the
  services substitute deterministic synthetic drivers (`driver_00…19`) and
  results differ. Same mechanics, different entrants — check
  `classification[*].driver_id` before comparing.
- **N=100 is a demo size.** Sampling noise is large (2nd decimal moves run
  to run *across seeds*; same seed is exact). Production inference uses
  N≥1000 with CI95 bands from the result payload.
- **Evidence tiers apply.** Strategy/setup/weather/race-control are
  `PRIOR_ONLY` priors and fuel is `NON_IDENTIFIABLE`: this example shows
  the machinery end-to-end, not a calibrated prediction of the real 2024
  Bahrain Grand Prix.
- **Exactness scope** (`docs/reproducibility.md`): same code + same
  environment + same `PYTHONHASHSEED`. Cross-platform byte identity is
  `NOT_VERIFIED`.
