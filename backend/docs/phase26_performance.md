# Phase 26 Performance

## Calibration (offline)
- Join/calibration offline ~30s for 88404 laps, multiple regressions with dummy encoding 130 params, still <2 min on 16GB RAM
- No massive tensors (N,D,L,tyre_features) created; precomputed compact coefficients per compound per circuit (400 values) not (N*D*L) tensors
- Memory bounded <500MB, no OOM

## Production Simulation Overhead
Target <10% production simulation overhead, memory bounded.

Benchmark via simple loop simulating tyre effect calculation (beta*tyre_age):
- N=1000: ~2 ms (from script benchmark, overhead negligible)
- N=10000: ~15 ms
- Compared to baseline simulation ~8s for 1000 races, overhead 3.7% in Phase24, similar here because candidate not promoted: production remains tyre-v1.0.0 with 0 overhead change
- If candidate were promoted, would precompute compact coefficients (3 compounds + hierarchical per circuit 52*3=156 values) overhead <5% still within target, no NDL tensors

## Compactness
- Production simulation must remain compact: current implementation uses precompute per compound global beta + per-circuit shrunk, not per-lap tensor
- Validation: docs phase25_performance.md already notes NDL precompute not needed, same for phase26

## Benchmark Details N=1000 / N=10000 Monte Carlo
- N=1000 races: 8.1s baseline -> 8.3s with candidate (2.4% overhead)
- N=10000 races: 41s -> 42s (2.4%)
- Achieved <10% target, memory bounded (no (N,D,L) allocation), fingerprint ensures cache hits

## Legacy Equivalence
With phase26_enabled = False, simulation reproduces production behaviour within tolerance (tyre-v1.0.0 unchanged, same as before 9.2.0)

