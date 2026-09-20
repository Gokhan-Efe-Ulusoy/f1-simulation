# Phase 27 Completion Report

Generated 2026-09-20T18:00:00+00:00
Dataset: f1-dataset-v1.3 laps 552656 valid 402199 after quality 81696 valid modern, pit 12747, stints 4840

## What Was Identifiable
- circuit: LIMITED hierarchical tau30/50, global 91.35, 36 circuits, improves 0.04-0.36 but last split worsens
- driver: LIMITED hierarchical tau10, per driver shrunk, not pure skill
- progression: RACE_PROGRESSION_ASSOCIATIONAL beta -6.53, NOT fuel
- pit: LIMITED mean 23.2 total only

## What Was Not Identifiable
- tyre degradation: NON_IDENTIFIABLE unconstrained -0.309 constrained 0.0 monotonic fails, all tests fail
- fuel: NON_IDENTIFIABLE actual fuel not available, proxy only
- constructor: LIMITED overall but NON_IDENTIFIABLE where n<30, driver-constructor confounding
- weather: PRIOR_ONLY wet 0 in filtered set
- race_control: PRIOR_ONLY SC/VSC sparse
- lane/stationary, tyre temp/pressure, setup telemetry, historical weather/strategy hidden team data all NON_IDENTIFIABLE

## What Improved
- Circuit baseline vs global: training 5.9 vs 6.5, validation 6.18 vs 6.23 improvement 0.047, second split 0.365

## What Worsened
- Full model with tyre worsens -1.25 for 2026, constructor adds +0.05
- Unconstrained tyre worsens due to inverted sign

## What Was Rejected
- Unconstrained tyre degradation
- Fuel as independent feature
- Lane/stationary, historical RC/weather inferred

## What Was Promoted
- Nothing promoted; KEEP_PRODUCTION_MODEL; candidates remain: circuit LIMITED, driver LIMITED, progression ASSOCIATIONAL, tyre NON_IDENTIFIABLE

## What Remained Candidate
- Circuit, driver, progression associational, pit LIMITED
- Tyre, fuel, weather, RC remain PRIOR_ONLY/NON_IDENTIFIABLE

## Why
Promotion gate requires all 10: physical sanity FAIL, walk_forward FAIL (not stable), no_major_confounding FAIL, so not promoted. Leakage 0, determinism PASS, falsification PASS, uncertainty reported, sample sufficient, provenance complete but 3 fail -> no promotion.

## Scientific Gate: FAIL (candidates not promoted, which is correct honest outcome, but overall Phase27 COMPLETE_WITH_LIMITATIONS)

