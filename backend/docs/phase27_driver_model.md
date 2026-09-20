# Phase 27 Driver Model

## Hierarchical driver pace: global -> era -> driver, optionally circuit-adjusted

Construction: residual after circuit baseline (lap_time - circuit_estimate), then hierarchical shrinkage global->driver tau10.

Do NOT interpret raw lap-time differences as pure driver skill; this is pace effect including car, tyre preservation not separated.

### Estimates
- Global driver mean 0 (by construction residual centered)
- Per driver:
  - n_laps 50-4500, n_circuits 10-30, n_seasons 1-4
  - raw: mean residual per driver e.g., driver 1 -0.307, driver 11 -0.374 etc (from phase26)
  - shrunk: (n*raw +10*global)/(n+10), e.g., driver 1 shrunk -0.307, dense 0.98 weight, sparse 0.4 weight
  - se: sd/sqrt(n) 0.02-0.15
  - circuits/seasons counted, shrinkage toward higher-level prior for sparse drivers (n<100 PRIOR_ONLY, 100-500 LIMITED, >=500 CALIBRATED)
- Circuit-adjusted driver effect: alternative fit where driver residual after circuit, vs driver alone (without circuit) would double-count circuit. We provide both but preferred circuit-adjusted.

## Identifiability
- Driver vs tyre preservation not separated: tyre age effect confounded, driver who preserves tyres may appear faster but not pure pace.
- Sparse drivers shrink heavily, not overfit.

## Walk-Forward
- Driver effect stability across splits similar to circuit: improves slightly 0.05-0.1 but not stable for 2026

## Tier
- Overall driver LIMITED (candidate)

