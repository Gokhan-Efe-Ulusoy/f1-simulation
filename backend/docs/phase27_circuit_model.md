# Phase 27 Circuit Model

## Candidate Hierarchical
Global 91.35s (valid filtered 2023-2026) vs Phase24 global 94.05 (all 552k laps). Difference due to valid subset faster modern cars. Both hierarchical tau30 circuit, tau50 era.

Era means (valid subset):
- 2022-2026: ~91.35 (global)
- Earlier eras not in valid subset but era_means from all laps: 1950-1960 ~98, 2014-2021 ~93 etc
- Estimable via full canonical but for phase27 valid subset only 2022-2026 has n>500

Per circuit (36 circuits in valid subset, vs 52 in full):
- n_laps 50-5000, n_races 2-10
- Example: albert_park n2108 raw 91.2 shrunk 91.3 se0.07 LIMITED? Actually n>400 CALIBRATED for many, but sparse circuits n<400 LIMITED, <50 PRIOR_ONLY
- Shrinkage weight w = n/(n+30), dense 0.98, sparse 0.6, not overfit
- CI: estimate ±1.96*se, e.g., monaco 92.5 ±0.04, losail small n 369 weight 0.86 shrunk heavily

## Evidence Tier
- CALIBRATED where n>=400 and n_races>=3
- LIMITED 50-400
- PRIOR_ONLY <50
- Overall circuit LIMITED (candidate)

## Walk-Forward
- Chronological: train <=2023 val 2024 baseline circuit mean 6.23 vs candidate 6.18 improvement 0.047
- Train <=2024 val 2025 8.41 vs 8.04 improvement 0.365
- Train <=2025 val 2026 5.96 vs 7.22 worsen -1.25 not stable
- Not future races used: strict_before, leakage 0
- Circuit alone improves 0.2-0.3 but not stable across last split due to 2026 small sample 16030

## Why Candidate Not Promoted
Still LIMITED, not stable across splits, last split worsens, plus overall promotion gate requires all components not just circuit.

## Fingerprint
Circuit estimate changes must change fingerprint via coefficients hash.

