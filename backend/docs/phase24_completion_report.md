# Phase24 Completion Report

WHAT WAS CALIBRATED: hierarchical circuit baseline (global->era->circuit->circuit×era) LIMITED candidate, pit total CALIBRATED, era CALIBRATED; WHAT NOT: tyre LIMITED, fuel NON_IDENTIFIABLE, weather/RC PRIOR_ONLY, setup/strategy NON_IDENTIFIABLE, driver/constructor LIMITED, sector/telemetry 0
WHY: walk-forward shows circuit reduces MAE 12.05->6.47 (~5.6s) stable across 10 splits but tyre/driver not improve, uncertainty high, sample sparse
DATA: 402199 VALID laps, 52 circuits, 7 eras, 913-1823 stints per compound, 12147 pits, leakage 0
REMAIN NON_IDENTIFIABLE: fuel exact, pit split, setup, strategy, historical tyre/weather, wet/dry per circuit
FAILED: tyre candidate hurts validation slightly, fuel not separable
IMPROVED: circuit-aware lap MAE 12.96->6.47 cross-circuit, within-circuit ~1.8; pit total robust
NOT IMPROVED: driver/constructor still LIMITED, weather/RC still PRIOR_ONLY
