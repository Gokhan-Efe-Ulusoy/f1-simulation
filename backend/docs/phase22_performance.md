# Phase 22 — Performance

*Measured on this repo, Windows, 2024-bahrain, 58 laps (full-length), seed 42. Cold = first leg incl. calibration/data load; warm = subsequent legs. Python process memory via tracemalloc peak.*

## 1. At N=1000 (the experimental scale)

`scripts/phase22_benchmark.py --n 1000 --points 5`:

```
cold_leg=110.6s  warm_leg=96.2s  counterfactual(both legs)=197.0s  sens5=526.2s  peak=122.1MB  sims_per_sec=10
```

Breakdown:

- One engine leg at N=1000, 58 laps dominates (~96-110s). The warm leg is ~96s because calibration JSON is cached; the cold leg adds dataset/manifest load.
- Full counterfactual experiment (`both legs + extended comparison + attribution`) at N=1000 is ~197s (two legs + sub-second comparison/attribution).
- OFAT sensitivity with 5 points at N=1000 is ~526s (baseline shared + 5 counterfactual legs). Scales linearly in `len(values)`; each leg is one `(N,D)` simulation (~96s).

The e2e strategy experiment (`pit [20,40]->[25,45]`, N=1000) measured `legs_time_s=142.5` + `sens_time_s=412.9` (includes artifact/report write) in a concurrent-process environment; hardware contention inflates both. The setup experiment at N=1000 measured `legs 160.8s sens 455.1s`; wet-weather `legs 251.3s sens 666.0s` (shared weather trajectories add outer-loop cost at 58 laps).

At N=10000 the N=200 warm-up probe measured `N=200, 58 laps -> 13.8s` (single leg, cold incl. lazy imports). Scaling is ~linear in N: N=1000 is ~70x over N=60 per leg. Projected N=10000 cold is `~1100s` single leg / `~2200s` counterfactual, which is why the e2e N=10000 run was sampled as a single distribution-contrast (55s for the shortened 6-lap verification leg vs 58-lap full length, see separately).

## 2. Tensor discipline

- Shapes remain `(N,D)` / `(N,L)` / `(N,L,S)` as appropriate (shared across drivers per lap for weather/race-control; per-driver for tyre age/compound/position). No `(N,D,L)` or `N x D x L x candidates x interventions` massive tensors are created. Sensitivity's bounded grid prevents combinatorial explosion; max 25 cells by assertion.
- Memory stays bounded: ~122 MB peak at N=1000 / 58 laps despite two simulation legs plus comparison/attribution. The kernels allocate `(N,D)` float arrays (20 drivers x N x float32 is ~80 kB per array at N=1000; the dominant allocations are weather trajectories `(N,L)=58k floats` x 4 arrays and race-control phase `(N,L)` ints). No leak across legs (per-leg `BatchState` is local).

## 3. Cold vs warm / cache

- First engine construction pays `~10-14s` for calibration JSON + canonical races/results load (even at `laps=6` the measured cold overhead is visible in test-suite logs: `core INFO Loading data for Bahrain...` repeated per scenario build). Subsequent legs hit the module-level caches (`calibration_state`, `WeatherEngine`/`RaceControlEngine` per-as_of) and stay deterministic with identical outputs.
- Processing order / batch partition invariance is tested at `N=60` (baseline legs of different counterfactuals identical -> no stream cross-talk). Cache invariants tested via post-branch re-run.

## 4. How to reproduce

```bash
python scripts/phase22_benchmark.py --n 1000 --points 5
python scripts/phase22_experiment_strategy.py --n 1000 --sens 1
python scripts/phase22_experiment_setup.py --n 1000
python scripts/phase22_experiment_weather.py --n 1000
```

Benchmarks exclude Python import/initialization (~3s) and report wall time from the first `ReplayEngine` call onward.

## 5. Limitations

- The 58-lap full-length legs are ~100x the cost of 6-lap test legs; CI keeps tests at 6-8 laps for that reason.
- `tracemalloc` peak under-reports NumPy contiguous-array memory (tracked as Python-owned but via the C allocator threshold), so the 122 MB figure is a lower bound; OS RSS would be higher.
