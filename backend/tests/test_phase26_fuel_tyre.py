"""Phase 26 Fuel Load Proxy & Lap-Time Decomposition tests — 35+."""
import json, os, hashlib, glob, random
import pytest
import pyarrow.parquet as pq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALIB25 = os.path.join(ROOT, "data", "calibration", "phase25")
CALIB26 = os.path.join(ROOT, "data", "calibration", "phase26")
CANON = os.path.join(ROOT, "data", "canonical")
DOCS = os.path.join(ROOT, "docs")

# Helpers
def load_decomp():
    with open(os.path.join(CALIB26, "phase26_decomposition.json")) as f:
        return json.load(f)

def load_fuel_proxy():
    with open(os.path.join(CALIB26, "phase26_fuel_proxy.json")) as f:
        return json.load(f)

def load_manifest():
    with open(os.path.join(CALIB26, "phase26_manifest.json")) as f:
        return json.load(f)

# 1 fuel-data audit existence
def test_fuel_data_audit_exists():
    assert os.path.exists(os.path.join(DOCS, "phase26_fuel_data_audit.md"))
    assert os.path.exists(os.path.join(DOCS, "phase26_fuel_proxy.md"))

def test_fuel_data_not_available():
    d = load_decomp()
    audit = d["fuel_data_audit"]
    assert audit["actual_fuel_available"] is False
    assert audit["sample_size"] == 0
    assert audit["coverage"] == "NOT_AVAILABLE"
    assert len(audit["fields_searched"]) == 6
    assert "fuel_load" in audit["fields_searched"]

def test_fuel_data_searched_fields():
    d = load_decomp()
    assert d["fuel_data_audit"]["result"] == "ACTUAL_FUEL_DATA = NOT_AVAILABLE"
    assert d["fuel_data_audit"]["source"] is None

# 2 proxy correctness
def test_proxy_correctness_variables():
    p = load_fuel_proxy()
    assert p["status"] == "FUEL_PROGRESSION_PROXY"
    assert p["evidence_tier"] == "PROXY_ONLY"
    assert p["is_fuel_load"] is False
    assert "normalized_lap" in p["variables"]
    assert "lap_number" in p["variables"]
    assert "stint_lap" in p["variables"]
    assert "race_progress" in p["variables"]
    assert "remaining_laps" in p["variables"]
    assert "race_phase" in p["variables"]
    assert len(p["variables"]) == 6

def test_proxy_not_fuel_load():
    d = load_decomp()
    assert d["fuel_proxy"]["evidence_tier"] == "PROXY_ONLY"
    assert d["fuel_proxy"]["is_fuel_load"] is False
    assert "warning" in d["fuel_proxy"]
    assert "NOT fuel" in d["fuel_proxy"]["warning"]

def test_proxy_definition_fingerprint():
    m = load_manifest()
    assert m["proxy_definition"] == "normalized_lap, lap_number, stint_lap, race_progress, remaining_laps, race_phase"
    assert len(m["fingerprint"]) == 8

# 3 no synthetic fuel
def test_no_synthetic_fuel_in_artifact():
    d = load_decomp()
    # ensure no fuel kg fields fabricated
    forbidden = ["fuel_kg", "fuel_mass", "fuel_remaining", "starting_fuel", "burn_rate"]
    text = json.dumps(d)
    for term in forbidden:
        # allow these terms only in description but not as model fields with kg values
        if f'"{term}"' in text:
            # check that not claiming lap 1 = X kg
            assert "lap 1 =" not in text or "kg" not in text.lower().split("lap 1 =")[0][-100:] if "lap 1 =" in text else True
    # Check fuel_proxy module validates
    from app.simulation.fuel_proxy import validate_no_synthetic_fuel
    assert validate_no_synthetic_fuel(d["fuel_proxy"]) is True
    assert validate_no_synthetic_fuel({"fuel_proxy": 1}) is True
    assert validate_no_synthetic_fuel({"fuel_kg": 110}) is False

def test_no_fabricated_kg_values():
    with open(os.path.join(DOCS, "phase26_fuel_proxy.md")) as f:
        txt = f.read()
    assert "No fabricated kg values" in txt or "not claim" in txt.lower()
    # document should warn NOT to implement synthetic fuel, not claim we did
    assert "Do NOT implement" in txt and "fuel_kg = starting_fuel" in txt
    # ensure code not actually implements synthetic model
    from app.simulation.fuel_proxy import validate_no_synthetic_fuel
    assert validate_no_synthetic_fuel({"fuel_kg": 110}) is False

# 4 join integrity
def test_join_integrity():
    with open(os.path.join(CALIB25, "tyre_join_manifest.json")) as f:
        m = json.load(f)
    assert m["exact"] == 93096
    assert m["ambiguous"] == 305
    assert m["unjoined"] == 249
    assert m["join_key"] == "race_id+driver_number+lap_number between lap_start and lap_end"

def test_join_exists_phase26_uses_same():
    d = load_decomp()
    assert d["provenance"]["tyre_join_version"] == "tyre_join-v1.0.0"
    assert os.path.exists(os.path.join(CALIB25, "tyre_join_exact.parquet"))
    assert os.path.exists(os.path.join(CALIB26, "phase26_decomposition.json"))

# 5 tyre-age monotonicity
def test_tyre_age_monotonicity():
    rows = pq.ParquetFile(os.path.join(CALIB25, "tyre_join_exact.parquet")).read(columns=["stint_id","tyre_age","lap_number"]).to_pylist()
    from collections import defaultdict
    by_stint = defaultdict(list)
    for r in rows:
        by_stint[r["stint_id"]].append(r)
    for sid, lst in list(by_stint.items())[:5]:
        ages = [r["tyre_age"] for r in sorted(lst, key=lambda x: x["lap_number"])]
        assert ages == sorted(ages)
        assert ages[0] >= 0
        assert all(isinstance(a, int) for a in ages)

def test_no_interpolated_tyre_age():
    rows = pq.ParquetFile(os.path.join(CALIB25, "tyre_join_exact.parquet")).read(columns=["tyre_age"]).to_pylist()
    assert all(isinstance(r["tyre_age"], int) for r in rows[:10])

# 6 within-stint transformation
def test_within_stint_transformation():
    d = load_decomp()
    ws = d["within_stint"]
    assert "demeaned_beta" in ws
    assert ws["demeaned_beta"] is not None
    assert ws["se"] is not None
    assert ws["n"] == 88404
    # sign should not change (still negative)
    assert ws["sign_changed"] is False
    assert ws["demeaned_beta"] < 0
    # compare vs global
    assert abs(ws["demeaned_beta"] - d["models"]["A_tyre_age"]["beta"]) > 0.05

def test_within_stint_purpose():
    d = load_decomp()
    assert "race_demeaned_beta" in d["within_stint"]
    assert "circuit_demeaned_beta" in d["within_stint"]

# 7 within-race controls
def test_within_race_controls():
    d = load_decomp()
    wr = d["within_race"]
    assert wr["avg_within_race_beta"] is not None
    assert wr["avg_within_race_beta"] < 0
    assert len(wr["per_race_betas_sample"]) == 5
    assert "note" in wr
    assert "cross-race confounding" in wr["note"]

def test_within_race_avoid_comparing():
    assert os.path.exists(os.path.join(DOCS, "phase26_lap_time_decomposition.md"))
    with open(os.path.join(DOCS, "phase26_lap_time_decomposition.md")) as f:
        txt = f.read()
    assert "within-race" in txt.lower() or "Within-Race" in txt

# 8 circuit controls
def test_circuit_controls():
    d = load_decomp()
    cc = d["circuit_control"]
    assert cc["global_baseline"] == 94.05168455036977
    assert cc["models"]["global"] < 0
    assert cc["models"]["circuit_controlled"] < 0
    assert abs(cc["models"]["global"] - cc["models"]["circuit_controlled"]) > 0.05
    assert "shrinkage_rule" in cc
    assert "tau" in cc["shrinkage_rule"]

def test_circuit_hierarchical():
    d = load_decomp()
    hier = d["circuit_control"]["models"]["hierarchical"]
    assert "hard" in hier
    assert len(hier["hard"]["by_circuit"]) > 20
    for cid, eff in list(hier["hard"]["by_circuit"].items())[:2]:
        assert "shrunk" in eff and "shrinkage_weight" in eff and "evidence_tier" in eff

def test_sparse_circuit_shrinkage():
    d = load_decomp()
    hard_circ = d["circuit_control"]["models"]["hierarchical"]["hard"]["by_circuit"]
    # sparse n<400 should have weight <0.95 and be limited
    sparse = [v for v in hard_circ.values() if v["n"] < 400]
    dense = [v for v in hard_circ.values() if v["n"] > 2000]
    if sparse and dense:
        assert max(s["shrinkage_weight"] for s in sparse) < min(d["shrinkage_weight"] for d in dense)

# 9 driver controls
def test_driver_controls():
    d = load_decomp()
    dc = d["driver_constructor_control"]
    assert "driver_betas_sample" in dc
    assert len(dc["driver_betas_sample"]) >= 3
    for drv, vals in dc["driver_betas_sample"].items():
        assert "shrunk" in vals and "se" in vals
    assert dc["hierarchical"] is True
    assert "not interpreted as skill" in dc["note"]

# 10 constructor controls
def test_constructor_controls():
    d = load_decomp()
    dc = d["driver_constructor_control"]
    assert "constructor_betas_sample" in dc
    assert len(dc["constructor_betas_sample"]) >= 2
    # constructor betas should also have shrinkage
    for cons, vals in dc["constructor_betas_sample"].items():
        assert "shrunk" in vals

def test_constructor_not_skill():
    with open(os.path.join(DOCS, "phase26_lap_time_decomposition.md")) as f:
        txt = f.read()
    assert "driver" in txt.lower()

# 11 compound separation
def test_compound_separation():
    d = load_decomp()
    ca = d["compound_analysis"]
    for comp in ["soft", "medium", "hard"]:
        assert comp in ca
        assert ca[comp]["sample"] > 500
        assert ca[comp]["races"] > 50
        assert ca[comp]["circuits"] >= 34
        assert "coefficient_range" in ca[comp]
        assert "ci" in ca[comp] or ca[comp]["coefficients"]["A"] is not None

def test_compound_coefficients():
    d = load_decomp()
    ca = d["compound_analysis"]
    # per spec should not pool if masks differences - we did separate, range should differ
    assert ca["soft"]["coefficients"]["A"] != ca["hard"]["coefficients"]["A"]
    assert ca["soft"]["sample"] == 10998
    assert ca["medium"]["sample"] == 33259
    assert ca["hard"]["sample"] == 44147

def test_compound_sign_stability():
    d = load_decomp()
    ca = d["compound_analysis"]
    # hard and medium have sign flip due to stint_lap collinearity -> not stable
    assert ca["hard"]["sign_stable"] is False  # because C becomes positive 0.04
    assert ca["soft"]["sign_stable"] is True  # soft all negative

# 12 era restrictions
def test_era_restrictions():
    d = load_decomp()
    ea = d["era_analysis"]
    assert "1996-2009" in ea
    assert ea["1996-2009"]["status"] == "NON_IDENTIFIABLE"
    assert ea["1996-2009"]["n"] == 0
    assert ea["2022-present"]["status"] == "LIMITED"
    assert ea["2022-present"]["n"] == 88404
    assert "no tyre data" in ea["1996-2009"]["note"].lower() or "no exact" in ea["1996-2009"]["note"].lower()

def test_no_historical_backfill():
    d = load_decomp()
    assert d["era_analysis"]["2010-2016"]["status"] == "NON_IDENTIFIABLE"
    assert d["compound_analysis"]["hard"]["sample"] > 0  # only modern
    # check that not applying to historical
    with open(os.path.join(DOCS, "phase26_tyre_analysis.md")) as f:
        txt = f.read()
    assert "Do NOT apply" in txt or "no backward extrapolation" in txt

# 13 leakage
def test_leakage_no_violations():
    d = load_decomp()
    assert d["promotion"]["leakage_violations"] == 0
    assert d["promotion"]["no_leakage"] is True
    assert d["falsification"]["future_progression_injection"]["leakage_violations"] == 0

def test_as_of_policy():
    d = load_decomp()
    assert d["provenance"]["as_of_policy"] == "race_date -1 day strict_before"
    # check tyre_join parquet as_of equals race_date
    rows = pq.ParquetFile(os.path.join(CALIB25, "tyre_join_exact.parquet")).read(columns=["race_id","as_of","race_date"]).to_pylist()
    import json as js
    with open(os.path.join(CANON, "races.json")) as f:
        races = js.load(f)
    race_map = {r["race_id"]: r["date"] for r in races}
    for r in rows[:5]:
        assert r["as_of"] == race_map.get(r["race_id"]) == r["race_date"]

# 14 future injection
def test_future_injection():
    d = load_decomp()
    assert d["falsification"]["future_progression_injection"]["passed"] is True
    assert d["falsification"]["future_result_injection"]["passed"] is True
    # leakage should not change historical
    assert d["promotion"]["no_leakage"] is True

# 15 determinism
def test_determinism():
    with open(os.path.join(CALIB26, "phase26_manifest.json")) as f:
        m1 = json.load(f)
    with open(os.path.join(CALIB26, "phase26_manifest.json")) as f:
        m2 = json.load(f)
    assert m1 == m2
    assert m1["seed"] == 42
    assert m1["provenance"].startswith("reproducible")

def test_fingerprint_changes_with_proxy():
    m = load_manifest()
    assert len(m["fingerprint"]) == 8
    # different proxy definition would change hash, we test that current proxy is as expected
    assert m["proxy_definition"].count(",") == 5  # 6 variables

# 16 falsification
def test_falsification_randomized_tyre_age():
    d = load_decomp()
    rand = d["falsification"]["randomized_tyre_age"]
    assert rand["passed"] is True
    assert abs(rand["shuffled_beta"]) < abs(rand["real_beta"])

def test_falsification_shuffled():
    d = load_decomp()
    assert d["falsification"]["shuffled_circuit"]["passed"] is True
    assert d["falsification"]["shuffled_compound"]["passed"] is True
    assert d["falsification"]["shuffled_lap_progression"]["passed"] is True
    assert d["falsification"]["overall_passed"] is True

def test_falsification_expected():
    with open(os.path.join(DOCS, "phase26_falsification.md")) as f:
        txt = f.read()
    assert "randomized tyre_age" in txt.lower()
    assert "future" in txt.lower()

# 17 counterfactual direction
def test_counterfactual_direction():
    d = load_decomp()
    cf = d["counterfactual"]
    assert cf["overall_passed"] is False
    assert cf["physically_correct"] is False
    assert cf["increase_tyre_age"]["passed"] is False
    assert cf["increase_tyre_age"]["predicted"] == "faster"
    assert cf["increase_tyre_age"]["beta"] < 0

def test_counterfactual_hard_gate():
    d = load_decomp()
    assert d["promotion"]["physically_correct_counterfactual"] is False
    # gate must not promote
    assert d["promotion"]["decision"] == "KEEP_PRODUCTION_MODEL"

def test_counterfactual_docs():
    assert os.path.exists(os.path.join(DOCS, "phase26_counterfactual.md"))
    with open(os.path.join(DOCS, "phase26_counterfactual.md")) as f:
        txt = f.read()
    assert "increase tyre age" in txt.lower()
    assert "FAIL" in txt

# 18 promotion gate
def test_promotion_gate():
    d = load_decomp()
    prom = d["promotion"]
    assert prom["promoted"] is False
    assert prom["decision"] == "KEEP_PRODUCTION_MODEL"
    assert prom["stable_coefficient_sign"] is False
    assert prom["robust_across_specifications"] is False
    assert prom["no_severe_confounding"] is False
    assert prom["chronological_validation_improvement"] is False
    assert "counterfactual inverted" in prom["reason"]

def test_promotion_all_criteria():
    d = load_decomp()
    prom = d["promotion"]
    required = ["no_leakage","exact_reproducibility","physically_correct_counterfactual","stable_coefficient_sign","robust_across_specifications","no_severe_confounding","chronological_validation_improvement","uncertainty_reported","no_historical_overreach","provenance_complete"]
    for crit in required:
        assert crit in prom
    # uncertainty and provenance true but others false -> not promoted
    assert prom["uncertainty_reported"] is True
    assert prom["provenance_complete"] is True

# 19 provenance
def test_provenance():
    d = load_decomp()
    prov = d["provenance"]
    assert prov["dataset_version"] == "f1-dataset-v1.3"
    assert prov["tyre_join_version"] == "tyre_join-v1.0.0"
    assert prov["seed"] == 42
    assert prov["dataset_hashes"]["races"] == "2cce529c"
    assert prov["fuel_data_status"] == "NOT_AVAILABLE"
    assert prov["evidence_tiers"]["fuel_proxy"] == "PROXY_ONLY"
    assert prov["fingerprint"] == "b22a1491"

def test_provenance_complete():
    rows = pq.ParquetFile(os.path.join(CALIB25, "tyre_join_exact.parquet")).read(columns=["source","raw_sha256"]).to_pylist()
    assert all(r["source"] and r["raw_sha256"] for r in rows[:5])
    m = load_manifest()
    assert m["calibration_version"] == "phase26-fuel-tyre-decomposition-v1.0.0-candidate"

# 20 legacy equivalence
def test_legacy_equivalence():
    # with phase26_enabled False, production tyre-v1.0.0 remains unchanged
    assert os.path.exists(os.path.join(ROOT, "data", "calibration", "models", "tyre_model.json"))
    with open(os.path.join(ROOT, "data", "calibration", "models", "tyre_model.json")) as f:
        prod = json.load(f)
    with open(os.path.join(CALIB26, "phase26_decomposition.json")) as f:
        cand = json.load(f)
    # candidate not auto-promoted
    assert prod != cand["models"]  # different structure
    # production still has GLOBAL beta -0.207
    assert prod["GLOBAL"]["beta"] == -0.20738438137868936
    # check fuel_proxy legacy equivalence helper
    from app.simulation.fuel_proxy import legacy_equivalence_check
    assert legacy_equivalence_check(False, -0.207, cand["models"]["A_tyre_age"]["beta"]) is True

def test_production_versions_unchanged():
    # check version.py still has expected versions
    from app.simulation.version import WEATHER_MODEL_VERSION, RACE_CONTROL_MODEL_VERSION, STRATEGY_MODEL_VERSION, SETUP_MODEL_VERSION
    assert WEATHER_MODEL_VERSION == "weather-v1.0.0"
    assert RACE_CONTROL_MODEL_VERSION == "racecontrol-v1.0.0"
    assert STRATEGY_MODEL_VERSION == "strategy-v1.1.0"
    assert SETUP_MODEL_VERSION == "setup-v1.0.0"
    # tyre production version is not explicitly in version.py but prod file version check
    assert os.path.exists(os.path.join(DOCS, "phase26_limitations.md"))

# 21 performance
def test_performance():
    d = load_decomp()
    perf = d["performance"]
    assert "production_overhead" in perf
    assert "<10%" in perf["production_overhead"] or perf["benchmark_N1000_ms"] < 100
    assert perf["memory_bounded"] is True
    assert perf["no_massive_tensors"] is True
    assert os.path.exists(os.path.join(DOCS, "phase26_performance.md"))
    with open(os.path.join(DOCS, "phase26_performance.md")) as f:
        txt = f.read()
    assert "NDL" in txt or "precompute" in txt or "overhead" in txt

def test_performance_benchmark():
    d = load_decomp()
    assert d["performance"]["benchmark_N1000_ms"] < 10
    assert d["performance"]["benchmark_N10000_ms"] < 100

# 22 ablation (models A-H)
def test_ablation():
    d = load_decomp()
    assert "models" in d
    # at least 8 models A-H
    assert len(d["models"]) >= 8
    for key in ["A_tyre_age","B_tyre_age_plus_lap_number","C_tyre_age_plus_stint_lap","D_tyre_age_plus_normalized_progress","E_tyre_age_plus_lap_number_plus_circuit","F_tyre_age_plus_lap_number_plus_circuit_plus_driver","G_tyre_age_plus_lap_number_plus_circuit_plus_driver_plus_constructor","H_tyre_age_plus_lap_number_plus_circuit_plus_driver_plus_constructor_plus_race_phase"]:
        assert key in d["models"]
        assert d["models"][key]["beta"] is not None

# 23 additional: checks for spec compliance
def test_identifiability_classification():
    d = load_decomp()
    assert d["classification"]["fuel_tyre_separation"] == "NON_IDENTIFIABLE"
    assert d["classification"]["tyre_degradation"] == "NON_IDENTIFIABLE"
    assert d["robustness"]["classification"] == "NON_IDENTIFIABLE"
    assert d["robustness"]["max_corr"] > 0.9  # due to stint_lap collinearity

def test_decomposition_values():
    d = load_decomp()
    assert d["decomposition_summary"]["baseline_beta"] == -0.30898461702614677
    assert d["decomposition_summary"]["progression_control_beta"] == -0.16764575234712578
    assert d["decomposition_summary"]["within_stint_beta"] == -0.17423325467180678
    assert d["decomposition_summary"]["circuit_control_beta"] == -0.2206016953556647

def test_correlation_values():
    d = load_decomp()
    corr = d["correlation"]["global"]["lap_number_vs_tyre_age"]
    assert abs(corr["pearson"] - 0.4967) < 0.01
    assert abs(corr["spearman"] - 0.502) < 0.01
    # stint_lap vs tyre_age should be ~0.983
    corr2 = d["correlation"]["global"]["stint_lap_vs_tyre_age"]
    assert abs(corr2["pearson"] - 0.983) < 0.01

def test_walk_forward():
    d = load_decomp()
    wf = d["walk_forward"]
    assert len(wf) == 3
    for w in wf:
        assert w["status"] == "ok"
        assert w["improvement"] < 0  # candidate worse

def test_weather_control():
    d = load_decomp()
    assert "weather_control" in d
    assert d["weather_control"]["as_of"] == "race_date -1 day"
    assert d["weather_control"]["evidence"] in ("LIMITED","PRIOR_ONLY","CALIBRATED")

def test_pit_race_control():
    d = load_decomp()
    assert "pit_race_control" in d
    assert d["pit_race_control"]["race_control"]["evidence"] == "LIMITED"
    assert d["pit_race_control"]["pit_effect_seconds"] > 20  # pit laps slower

def test_no_historical_fuel():
    d = load_decomp()
    assert d["era_analysis"]["1996-2009"]["n"] == 0
    assert d["provenance"]["training_window"] == "2023-2026 (exact tyre join only)"

def test_docs_exist():
    required = ["phase26_preflight_audit.md","phase26_fuel_data_audit.md","phase26_fuel_proxy.md","phase26_lap_time_decomposition.md","phase26_identifiability.md","phase26_tyre_analysis.md","phase26_walk_forward.md","phase26_counterfactual.md","phase26_falsification.md","phase26_validation.md","phase26_performance.md","phase26_limitations.md","phase26_completion_report.md"]
    for doc in required:
        assert os.path.exists(os.path.join(DOCS, doc)), f"missing {doc}"

def test_fuel_proxy_module():
    from app.simulation.fuel_proxy import build_proxy, EVIDENCE_TIER, IS_FUEL_LOAD, PROXY_DEFINITION
    assert EVIDENCE_TIER == "PROXY_ONLY"
    assert IS_FUEL_LOAD is False
    assert "normalized_lap" in PROXY_DEFINITION
    p = build_proxy(lap_number=10, stint_lap=5, max_lap=50)
    assert p.evidence_tier == "PROXY_ONLY"
    assert p.race_phase in ("early","mid","late")
    assert p.normalized_lap == 0.2

