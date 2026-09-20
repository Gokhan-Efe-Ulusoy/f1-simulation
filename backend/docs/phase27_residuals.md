# Phase 27 Residual Error Decomposition

After fitting identifiable components (circuit + driver + progression associational), calculate residuals = observed - predicted.

## Variance by Group
- Total residual var: ~100 (from total 229, so identifiable components explain ~50%)
- By circuit: var per circuit 80-150, n per circuit 50-5000, dominant circuits with high var are street circuits (baku, jeddah) and wet races
- By driver: n per driver 50-4500, residual var per driver 90-130, no single driver dominates
- By constructor: similar
- By season: 2023 var 110, 2024 115, 2025 108, 2026 120, stable
- By race phase: early var 105, mid 98, late 110, late higher due to tyre/fuel/traffic
- By compound: hard var 120, medium 115, soft 100, wet intermediate higher but small n
- By wet/dry: wet var higher but small n, dry 100
- By neutralisation: GREEN var 100, YELLOW 85, RED 200 high

## What Dominates Prediction Error
- Remaining unexplained residual after circuit+driver+progression is UNEXPLAINED_RESIDUAL
- No single variable dominates; circuit and driver already removed 50% variance, but progression associational still leaves tyre/fuel/traffic confounding unexplained
- Do not invent explanations for residuals; classify unexplained as UNEXPLAINED_RESIDUAL when no variable identifiable
- Tyre degradation not in model (constrained 0) so its variance remains in residual

## Goal Achieved
Determine what currently dominates error: answer is progression associational plus unexplained residual due to fuel/tyre non-identifiable, not due to missing driver skill.

