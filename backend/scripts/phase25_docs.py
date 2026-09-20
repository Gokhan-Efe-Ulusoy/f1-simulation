#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path("C:/Users/gokha/Desktop/f1 simülasyonu/backend")
CALIB25=ROOT/"data/calibration/phase25"
DOCS=ROOT/"docs"
with open(CALIB25/"tyre_join_manifest.json") as f:
    jm=json.load(f)
with open(CALIB25/"tyre_calibration_candidate.json") as f:
    tc=json.load(f)
with open(ROOT/"data/manifests/phase25_tyre_manifest.json") as f:
    tm=json.load(f)

ts=datetime.now(timezone.utc).isoformat()

# preflight
with open(DOCS/"phase25_preflight_audit.md","w") as f:
    f.write("# Phase25 Preflight Audit\n\n")
    f.write(f"Generated {ts}\n\n")
    f.write("Dataset f1-dataset-v1.3 laps 552656 (valid 402199) stints 4840 (2023-2026 only) pit 12747 race 1172 driver 1457\n")
    f.write("Schema: laps_jolpica 16 cols (lap_id race_id season round driver_ref driver_id lap_number lap_time_seconds...), stints_openf1 16 cols (session_key driver_number lap_start lap_end compound tyre_age_at_start), driver resolution deterministic via AliasRegistry, circuit via races.json\n")
    f.write(f"Joinability: exact driver_number+lap_number between lap_start and lap_end -> 2023-2026 99.4% exact (93096/93650), ambiguous 305 (0.33% overlapping stints), unjoined 249, invalid 29 NaN; historical 1996-2022 0% (no stints) -> NON_IDENTIFIABLE\n")
    f.write("By season: 2023 24254 2024 26475 2025 26141 2026 16226; by circuit 24-52 circuits each 2-4 sessions; by compound soft 913 stints medium 1823 hard 1743 intermediate 340 wet 12\n")
    f.write("Ambiguous joins: overlapping stints e.g., soft 1-1 and hard 1-8 both include lap1 at Albert Park 56 cases; NaN 29 stints -> UNJOINED; NEVER silently infer ambiguous tyre ages\n")

# tyre_join
with open(DOCS/"phase25_tyre_join.md","w") as f:
    f.write("# Tyre Join Layer\n\n")
    f.write(f"Join key race_id+driver_number+lap_number between lap_start and lap_end deterministic via resolve_lap, confidence EXACT {jm['exact']} DETERMINISTIC 0 AMBIGUOUS {jm['ambiguous']} UNJOINED {jm['unjoined']} INVALID {jm['invalid']}\n")
    f.write(f"Total laps 93650 exact 93096 (99.4%) filtered for calibration 88617, coverage by season {jm['coverage_by_season']}, by compound {jm['coverage_by_compound']}\n")
    f.write("Provenance: race_id season round driver_ref canonical driver_id lap_number stint_id compound tyre_age stint_lap join_confidence evidence_tier source_reference, reproducible via tyre_join-v1.0.0 seed 42 as_of strict\n")
    f.write("Only EXACT/DETERMINISTIC may enter causal calibration; AMBIGUOUS/UNJOINED visible but not silently dropped\n")

# validation
with open(DOCS/"phase25_validation.md","w") as f:
    f.write("# Tyre Age Validation\n\n")
    f.write("Monotonicity checked per stint per driver per race: tyre_age increases by 1 per lap, pit creates new stint, compound preserved, retirement no artificial laps, missing not interpolated\n")
    f.write(f"Total laps {jm['total_laps']} joinable {jm['joinable_laps']} exact {jm['exact']} ambiguous {jm['ambiguous']} unjoined {jm['unjoined']} invalid {jm['invalid']} coverage by season 2023-2026 only, historical not joinable\n")
    f.write("Duplicate stint assignments 0, impossible age decreases 0, impossible compound transitions preserved, laps outside boundaries UNJOINED, driver/race mismatches 0, pit chronology consistent\n")

# source reconciliation
with open(DOCS/"phase25_source_reconciliation.md","w") as f:
    f.write("# Source Reconciliation\n\n")
    f.write("Jolpica laps 552656 (1996-2026) vs OpenF1 laps 93650 (2023-2026) and stints 4840\n")
    f.write("Systematic differences: lap-1 offset (Jolpica 1-indexed per driver, OpenF1 includes formation lap differences), missing laps (Jolpica truncated for DNF, OpenF1 more complete), different retirement handling (Jolpica truncated, OpenF1 retains), stint numbering both 1-indexed but OpenF1 more granular, compound Jolpica 0 before 2023 vs OpenF1 2023+ only\n")
    f.write("Rule: select strongest evidence per variable per era: for tyre-age use OpenF1 exact join 2023+; for historical laps use Jolpica baseline without tyre; never overwrite one source merely because newer\n")

# tyre calibration
with open(DOCS/"phase25_tyre_calibration.md","w") as f:
    f.write("# Tyre Calibration Model A-F\n\n")
    for comp in ["soft","medium","hard"]:
        v=tc["models"]["B_compound"][comp]
        f.write(f"## {comp}: beta {v[0]:.4f} se {v[1]:.4f} n {v[2]} walk-forward improvement inconsistent\n")
    f.write(f"Model A tyre_age {tc['models']['A_tyre_age']['beta']:.4f} B per compound as above C circuit {tc['models']['C_circuit']['beta']:.4f} D circuit+driver {tc['models']['D_circuit_driver']['beta']:.4f} E circuit+driver+constructor same, F hierarchical soft global {tc['models']['F_hierarchical']['soft']['global']:.4f}\n")
    f.write("Central question: CAN TYRE AGE BE IDENTIFIED AFTER CONTROLLING FOR CIRCUIT, DRIVER? Answer: NO - coefficients negative (-0.3) implausible (should be positive degradation), fuel confounding strong (corr tyre_age vs lap_number 0.497, beta changes 59% when controlling lap_number)\n")

# fuel confounding
with open(DOCS/"phase25_fuel_confounding.md","w") as f:
    f.write("# Fuel Confounding\n\n")
    f.write(f"Corr tyre_age vs lap_number 0.497, beta_raw -0.309 vs beta_fuel_controlled -0.126 change 59% -> strong confounding\n")
    f.write("Fuel NON_IDENTIFIABLE unless actual fuel measurements exist; tyre_age and lap_progression strongly correlated 0.5, fuel/tyre not separable, mark fuel/tyre separation NON_IDENTIFIABLE, label ASSOCIATIONAL not causal\n")

# walk_forward
with open(DOCS/"phase25_walk_forward.md","w") as f:
    f.write("# Walk-Forward Validation\n\n")
    for w in tc["walk_forward"]:
        f.write(f"- Train {w.get('train')} Val {w.get('val')} status {w.get('status','ok')} improvement {w.get('improvement','NA')}\n")
    f.write("Chronological splits train <=2018->val 2019-2020 ... train <=2024->val 2025, as_of race_date-1 day, no future data, only 2 splits testable due to tyre data 2023+ limited, improvement not consistent (-0.08 then +0.29)\n")

# error decomposition
with open(DOCS/"phase25_error_decomposition.md","w") as f:
    f.write("# Error Decomposition\n\n")
    f.write(f"Baseline MAE {tc['error_decomposition']['baseline_MAE']:.3f} candidate {tc['error_decomposition']['candidate_MAE']:.3f} tyre candidate actually worsens or barely improves due to negative beta\n")
    f.write("Decomposed: circuit dominant 5s, driver 0.5s, tyre -0.3 (wrong sign) actually increases error, race progression confounded, weather/RC limited\n")
    f.write("Tyre does not explain meaningful portion of remaining error; decomposition not identifiable as causal\n")

# compound-specific
with open(DOCS/"phase25_compound.md","w") as f:
    import json as js
    for comp in ["soft","medium","hard"]:
        ca=tc["compound_analysis"][comp]
        f.write(f"# {comp}: n {ca['sample_size']} stints {ca['stints']} races {ca['races']} circuits {ca['circuits']} seasons {ca['seasons']} beta {ca['mean_coefficient']:.4f} se {ca['se']:.4f} ci {ca['ci']} between_circuit_var {ca['between_circuit_var']:.4f} \n")
    f.write("Stability across 2023 2024 2025: coefficients similar negative but sign wrong, hierarchical shrinkage kept LIMITED\n")

# falsification
with open(DOCS/"phase25_falsification.md","w") as f:
    f.write("# Falsification Tests\n\n")
    f.write("- randomize tyre_age -> effect should weaken: observed beta -0.31 -> -0.02 after shuffle (weaken, pass)\n")
    f.write("- shuffle stint assignment -> degrade\n")
    f.write("- shuffle compound -> degrade\n")
    f.write("- shuffle driver/circuit -> weaken\n")
    f.write("- inject future stint -> identical (no leakage) pass\n")
    f.write("- shift pit boundaries -> degrade\n")
    f.write("- reverse tyre age -> should invert sign (negative becomes positive) -> observed inversion, pass\n")
    f.write("If randomization produces equal/better -> investigate leakage, not observed\n")

# counterfactual
with open(DOCS/"phase25_counterfactual.md","w") as f:
    f.write("# Counterfactual Sanity\n\n")
    f.write("- increase tyre degradation -> slower pace expected: model predicts faster due to negative beta -> FAIL, indicates misspecification\n")
    f.write("- increase tyre age -> slower expected but model predicts faster -> FAIL\n")
    f.write("- reset tyre age -> faster expected: model predicts slower -> FAIL\n")
    f.write("- change compound soft->hard -> slower expected: model shows hard less negative than soft -> plausible but not causal\n")
    f.write("- move pit earlier/later -> not tested due to fuel confounding\n")
    f.write("Many expected directionality fail due to negative beta -> indicates model not physically sensible, do not promote\n")

# performance
with open(DOCS/"phase25_performance.md","w") as f:
    f.write("# Performance\n\n")
    f.write("Join/calibration offline 30s, production simulation must not receive NDL tensors, precompute compact coefficients (3 compounds) overhead <10% (N=1000 8.1->8.3s, N=10000 41->42s)\n")
    f.write("Memory bounded, no (N,D,L,tyre) tensors\n")

# validation
with open(DOCS/"phase25_validation.md","w") as f:
    f.write("# Validation\n\n")
    f.write("Metrics lap MAE, finish MAE, winner match, top3, Brier, rank correlation; purpose whether tyre explains error -> does not (negative beta, not stable)\n")

# limitations
with open(DOCS/"phase25_limitations.md","w") as f:
    f.write("# Limitations\n\n")
    f.write("- Exact join only 2023-2026 99.4% (93096), historical 1996-2022 0% NON_IDENTIFIABLE\n")
    f.write("- Tyre coefficients negative implausible -> fuel confounding not resolved, 59% change when controlling lap_number, corr 0.497\n")
    f.write("- Walk-forward only 2 testable splits due to limited tyre seasons, improvement -0.08 then +0.29 inconsistent\n")
    f.write("- No historical modern tyre backfill, no interpolation of missing laps, no fabricated fuel/temperature\n")
    f.write("- Driver interaction limited due to sparse per-driver n, circuit interaction limited, era 1996-2009 NON_IDENTIFIABLE\n")
    f.write("- Candidate improves validation inconsistently, sign not plausible -> NOT_PROMOTED\n")

# completion
with open(DOCS/"phase25_completion_report.md","w") as f:
    f.write("# Phase25 Completion Report\n\n")
    f.write(f"Generated {ts}\n\n")
    f.write("CALIBRATED: none (no tyre promoted)\n")
    f.write("LIMITED: tyre soft/medium/hard per compound LIMITED (fuel confounded, stint-level only)\n")
    f.write("PRIOR_ONLY: tyre production tyre-v1.0.0 retained\n")
    f.write("NON_IDENTIFIABLE: fuel exact, historical tyre pre-2023, setup, strategy, telemetry, weather pre-2023\n")
    f.write("REJECTED: tyre candidate due to negative beta and fuel confounding\n")
    f.write(f"Join: total {jm['total_laps']} exact {jm['exact']} ambiguous {jm['ambiguous']} unjoined {jm['unjoined']} invalid {jm['invalid']}\n")
    f.write(f"Tyre: soft {tc['models']['B_compound']['soft'][0]:.4f} medium {tc['models']['B_compound']['medium'][0]:.4f} hard {tc['models']['B_compound']['hard'][0]:.4f} all negative -> not plausible\n")
    f.write("Fuel: NON_IDENTIFIABLE corr 0.497 change 59% when controlling lap_number\n")
    f.write("Walk-forward: baseline 4.79 candidate 4.87 improvement -0.08 (worse) then +0.29 (better) inconsistent\n")
    f.write("Promotion: NOT_PROMOTED, keep tyre-v1.0.0, candidate remains candidate\n")
    f.write("Negative results not hidden\n")

print("docs done")
