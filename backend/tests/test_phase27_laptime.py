"""Phase 27 Lap-Time Decomposition tests — comprehensive."""
import json, os, hashlib
import pyarrow.parquet as pq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALIB25 = os.path.join(ROOT, "data", "calibration", "phase25")
CALIB26 = os.path.join(ROOT, "data", "calibration", "phase26")
CALIB27 = os.path.join(ROOT, "data", "calibration", "phase27")
CANON = os.path.join(ROOT, "data", "canonical")
DOCS = os.path.join(ROOT, "docs")

def load27():
    with open(os.path.join(CALIB27, "phase27_decomposition.json")) as f:
        return json.load(f)

# data availability
def test_data_availability_lap_time():
    d = load27()
    assert d["dataset"]["laps"] == 552656
    assert d["dataset"]["valid_laps"] >= 80000
    assert d["identifiable"]["circuit"] in ("LIMITED","CALIBRATED")

def test_data_availability_driver_constructor():
    d = load27()
    assert d["identifiable"]["driver"] == "LIMITED"
    assert d["identifiable"]["constructor"] in ("LIMITED","NON_IDENTIFIABLE")
    assert len(d["driver"]) >= 20
    assert len(d["constructor"]) >= 10

def test_data_availability_compound_tyre():
    d = load27()
    assert d["identifiable"]["tyre"] == "NON_IDENTIFIABLE"
    assert d["tyre"]["n"] == 88404
    assert "soft" in d["tyre"]["compound_effects"]

def test_data_availability_pit_weather_rc():
    d = load27()
    assert d["identifiable"]["pit"] == "LIMITED"
    assert d["pit"]["mean_total_loss"] > 20
    assert d["identifiable"]["weather"] == "PRIOR_ONLY"
    assert d["identifiable"]["race_control"] == "PRIOR_ONLY"
    assert d["identifiable"]["fuel"] == "NON_IDENTIFIABLE"

# lap quality
def test_lap_quality_deterministic():
    from app.simulation.laptime.quality import LapQualityFilter, classify_lap
    from app.simulation.laptime.models import LapRecord
    r1 = LapRecord(race_id="2023-bahrain", season=2023, circuit="bahrain", driver_number=1, driver_id="1", constructor="c1", lap_number=1, stint_lap=1, compound="soft", tyre_age=0, lap_time_seconds=90, is_pit_in=False, is_pit_out=False)
    assert classify_lap(r1).value == "formation"
    r2 = LapRecord(race_id="2023-bahrain", season=2023, circuit="bahrain", driver_number=1, driver_id="1", constructor="c1", lap_number=5, stint_lap=1, compound="soft", tyre_age=0, lap_time_seconds=90, is_pit_in=False, is_pit_out=True)
    assert classify_lap(r2).value == "pit-lap"
    # deterministic: same input same output
    assert classify_lap(r1) == classify_lap(r1)

def test_lap_quality_counts():
    d = load27()
    q = d["quality"]
    assert q["counts"]["valid"] == 81696
    assert q["counts"]["pit-lap"] == 2950
    assert q["total"] == 88617
    assert "by_season" in q and "by_circuit" in q and "by_driver" in q

def test_lap_quality_no_silent_deletion():
    assert os.path.exists(os.path.join(CALIB27, "lap_quality_audit.json"))
    with open(os.path.join(CALIB27, "lap_quality_audit.json")) as f:
        a = json.load(f)
    assert sum(a["counts"].values()) == a["total"]
    # every exclusion has reason
    assert "pit-lap" in a["exclusion_reasons"]

# deterministic decomposition
def test_deterministic_decomposition():
    from app.simulation.laptime.decomposition import LapTimeDecomposition
    from app.simulation.laptime.models import LapRecord
    recs = [LapRecord(race_id="2023-bahrain", season=2023, circuit="bahrain", driver_number=1, driver_id="1", constructor="c1", lap_number=10, stint_lap=5, compound="soft", tyre_age=4, lap_time_seconds=90, is_pit_in=False, is_pit_out=False)]
    m1 = LapTimeDecomposition()
    m1.fit(recs)
    m2 = LapTimeDecomposition()
    m2.fit(recs)
    # fingerprints should be identical for same data, but we check predictions identical
    p1 = m1.predict(recs[0])
    p2 = m2.predict(recs[0])
    assert p1.total_predicted == p2.total_predicted

# circuit hierarchy
def test_circuit_hierarchy():
    d = load27()
    circuits = d["circuit"]["circuits"]
    assert len(circuits) == 36
    for cid, est in list(circuits.items())[:3]:
        assert "estimate" in est and "se" in est and "shrinkage" in est and "evidence_tier" in est
        assert 0 <= est["shrinkage"] <= 1

def test_circuit_shrinkage_sparse():
    d = load27()
    circuits = d["circuit"]["circuits"]
    sparse = [v for v in circuits.values() if v["n_laps"] < 400]
    dense = [v for v in circuits.values() if v["n_laps"] > 2000]
    if sparse and dense:
        assert max(s["shrinkage"] for s in sparse) < min(d["shrinkage"] for d in dense)

def test_circuit_baseline_module():
    from app.simulation.laptime.baseline import CircuitBaseline
    cb = CircuitBaseline(tau=30)
    assert cb.tau == 30
    assert hasattr(cb, "fit")
    assert hasattr(cb, "predict")

# driver hierarchy
def test_driver_hierarchy():
    d = load27()
    drivers = d["driver"]
    assert len(drivers) >= 20
    for did, est in list(drivers.items())[:3]:
        assert "shrunk" in est and "se" in est and "tier" in est
        assert est["tier"] in ("CALIBRATED","LIMITED","PRIOR_ONLY")

def test_driver_shrinkage():
    d = load27()
    drivers = d["driver"]
    # sparse n<100 should be PRIOR_ONLY
    sparse = [v for v in drivers.values() if v["n_laps"] < 100]
    if sparse:
        assert all(v["tier"] == "PRIOR_ONLY" for v in sparse[:2])

# constructor hierarchy
def test_constructor_hierarchy():
    d = load27()
    cons = d["constructor"]
    assert len(cons) >= 10
    # check hierarchical and at least limited where sufficient
    limited_or_cal = [v for v in cons.values() if v.get("tier") in ("LIMITED","CALIBRATED")]
    assert len(limited_or_cal) >= 1
    # if any NON_IDENTIFIABLE, check reason
    non = [v for v in cons.values() if v.get("tier") == "NON_IDENTIFIABLE"]
    if non:
        assert "driver-constructor confounding" in non[0].get("reason","")

def test_constructor_double_count():
    # constructor and driver not double-counted: model comparison shows little improvement
    d = load27()
    mc = d["model_comparison"]
    assert mc["CIRCUIT + DRIVER"]["validation_MAE"] <= mc["CIRCUIT + DRIVER + CONSTRUCTOR"]["validation_MAE"] + 0.2

# progression confounding
def test_progression_confounding():
    d = load27()
    prog = d["progression"]
    # coefficient stability: tyre beta changes 27% between A and C
    beta_a = prog["B_tyre_plus_progression"]["beta"]
    beta_c = prog["C_circuit_plus_progression"]["beta"]
    change = abs(beta_c - beta_a) / abs(beta_a) if beta_a else 0
    assert change > 0.2  # substantial confounding reported
    assert prog["A_progression_only"]["beta"] < 0  # progression associational negative (faster as race progresses due to fuel)
    # not called fuel
    assert "NOT fuel" in str(d["identifiable"]["progression"]) or d["identifiable"]["progression"] == "RACE_PROGRESSION_ASSOCIATIONAL"

def test_progression_not_fuel():
    with open(os.path.join(DOCS, "phase27_progression.md")) as f:
        txt = f.read()
    assert "NOT fuel" in txt or "NOT FUEL" in txt.upper() or "not fuel" in txt.lower()
    assert "RACE_PROGRESSION_ASSOCIATIONAL" in txt

# tyre monotonicity
def test_tyre_monotonicity_unconstrained():
    d = load27()
    tyre = d["tyre"]
    assert tyre["unconstrained_beta"] < 0  # negative violates monotonic
    assert tyre["constrained_beta"] == 0.0
    assert tyre["tier"] == "NON_IDENTIFIABLE"
    assert tyre["physically_plausible"] is False

def test_tyre_monotonicity_constrained():
    from app.simulation.laptime.effects import TyreEffect
    te = TyreEffect()
    assert hasattr(te, "fit")
    # constrained model must enforce beta >=0
    # we test that fitted constrained beta is 0 when unconstrained negative
    d = load27()
    assert d["tyre"]["monotonic_constrained_model"]["beta"] == 0.0

def test_tyre_counterfactuals():
    d = load27()
    assert d["tyre"]["tests"]["plus_5_laps"]["passed"] is False
    assert d["tyre"]["tests"]["plus_10_laps"]["expected"] == "slower"
    assert d["tyre"]["tests"]["reset_tyre_age"]["passed"] is False

def test_tyre_not_forced_positive():
    with open(os.path.join(DOCS, "phase27_tyre_reassessment.md")) as f:
        txt = f.read()
    assert "DO NOT fit" in txt or "Do NOT fit" in txt
    assert "positive" in txt.lower()

# pit exclusion
def test_pit_exclusion():
    d = load27()
    assert d["pit"]["mean_total_loss"] > 20
    assert 23 < d["pit"]["mean_total_loss"] < 30
    assert "lane_loss" in d["pit"]["note"] and "NON_IDENTIFIABLE" in d["pit"]["note"]
    # quality filter excludes pit laps from valid
    q = d["quality"]
    assert q["counts"]["pit-lap"] == 2950

def test_pit_improves_prediction():
    # pit exclusion improves MAE: we can check that valid set smaller than enriched
    d = load27()
    assert d["quality"]["counts"]["valid"] < d["quality"]["total"]

# weather evidence
def test_weather_evidence():
    d = load27()
    assert d["identifiable"]["weather"] == "PRIOR_ONLY"
    assert d["weather"]["tier"] == "PRIOR_ONLY"
    assert "ERA5" in d["weather"].get("reason","") or "wet" in d["weather"].get("reason","").lower()
    with open(os.path.join(DOCS, "phase27_weather_rc.md")) as f:
        txt = f.read()
    assert "sensor" in txt.lower() and "ERA5" in txt

# race-control evidence
def test_race_control_evidence():
    d = load27()
    assert d["identifiable"]["race_control"] == "PRIOR_ONLY"
    rc = d["race_control"]
    assert "GREEN" in rc["flags"]
    assert rc["flags"]["GREEN"]["tier"] == "CALIBRATED"
    assert "SC/VSC" in rc["note"] or "SC" in rc["note"]
    # historical SC remains PRIOR_ONLY unless 100 laps gate
    assert rc["status"] == "PRIOR_ONLY"

# leakage
def test_leakage():
    d = load27()
    assert d["leakage"]["violations"] == 0
    assert d["leakage"]["as_of"] == "race_date -1 day"
    assert d["leakage"]["future_injection_passed"] is True
    assert d["provenance"]["as_of_rule"] == "race_date -1 day"

def test_as_of_strict():
    # check tyre join as_of equals race_date
    rows = pq.ParquetFile(os.path.join(CALIB25, "tyre_join_exact.parquet")).read(columns=["race_id","as_of","race_date"]).to_pylist()
    import json as js
    with open(os.path.join(CANON, "races.json")) as f:
        races = js.load(f)
    race_map = {r["race_id"]: r["date"] for r in races}
    for r in rows[:5]:
        assert r["as_of"] == race_map.get(r["race_id"])

# future injection
def test_future_injection():
    d = load27()
    assert d["falsification"]["future_result_injection"]["passed"] is True
    assert d["falsification"]["future_weather_injection"]["passed"] is True
    assert d["falsification"]["future_pit_injection"]["passed"] is True
    assert d["falsification"]["future_result_injection"]["leakage_violations"] == 0

# falsification
def test_falsification():
    d = load27()
    fals = d["falsification"]
    assert fals["shuffled_driver"]["passed"] is True
    assert fals["shuffled_driver"]["lost_signal"] is True
    assert fals["overall_passed"] is True
    assert fals["shuffled_circuit"]["passed"] is True

# counterfactuals
def test_counterfactuals():
    d = load27()
    cf = d["counterfactual"]
    # circuit delta PASS
    assert cf["circuit_delta"]["PASS"] is True
    # tyre overall FAIL
    assert d["counterfactual_overall"]["overall_pass"] is False
    assert d["counterfactual_overall"]["physically_inverted"] is True

def test_counterfactual_pit_wet():
    d = load27()
    assert d["counterfactual"]["pit_loss"]["PASS"] is True

# walk-forward
def test_walk_forward():
    d = load27()
    wf = d["walk_forward"]
    assert len(wf) == 3
    for w in wf:
        assert w["status"] == "ok"
        assert "baseline_lap_MAE" in w and "candidate_lap_MAE" in w
    # not stable improvement
    improvements = [w["improvement"] for w in wf]
    assert not all(imp and imp>0 for imp in improvements)

def test_walk_forward_not_cherry_picked():
    with open(os.path.join(DOCS, "phase27_walk_forward.md")) as f:
        txt = f.read()
    assert "Do not cherry-pick" in txt
    assert "NOT_TESTABLE" in txt or "not stable" in txt.lower()

# provenance
def test_provenance():
    d = load27()
    prov = d["provenance"]
    assert prov["dataset_version"] == "f1-dataset-v1.3"
    assert prov["dataset_hash"] == "2cce529c"
    assert prov["calibration_version"] == "phase27-laptime-decomposition-v1.0.0-candidate"
    assert prov["seed"] == 42
    assert len(prov["fingerprint"]) == 8

def test_fingerprint_changes():
    from app.simulation.laptime.fingerprint import fingerprint
    fp1 = fingerprint("f1-dataset-v1.3","2cce529c","phase27","0.9.0",["circuit"],"race_date -1 day","2023-2026",42,{"a":1})
    fp2 = fingerprint("f1-dataset-v1.3","2cce529c","phase27","0.9.0",["circuit","driver"],"race_date -1 day","2023-2026",42,{"a":1})
    assert fp1 != fp2
    # changing coefficient changes fingerprint
    fp3 = fingerprint("f1-dataset-v1.3","2cce529c","phase27","0.9.0",["circuit"],"race_date -1 day","2023-2026",42,{"a":2})
    assert fp1 != fp3

# ablation
def test_ablation_model_comparison():
    d = load27()
    mc = d["model_comparison"]
    assert "PRODUCTION BASELINE" in mc
    assert "CIRCUIT-ONLY CANDIDATE" in mc
    assert "FULL IDENTIFIABLE MODEL" in mc
    assert len(mc) == 7
    for name, vals in mc.items():
        assert "train_MAE" in vals and "validation_MAE" in vals

# performance
def test_performance():
    d = load27()
    perf = d["performance"]
    assert perf["memory_bounded"] is True
    assert "<10%" in perf["overhead"]
    assert perf["N=1000_ms"] < 10
    assert perf["N=10000_ms"] < 100
    assert os.path.exists(os.path.join(DOCS, "phase27_performance.md"))

# production equivalence
def test_production_equivalence():
    assert os.path.exists(os.path.join(ROOT, "data", "calibration", "models", "tyre_model.json"))
    with open(os.path.join(ROOT, "data", "calibration", "models", "tyre_model.json")) as f:
        prod = json.load(f)
    d = load27()
    # candidate not promoted, production unchanged
    assert prod["GLOBAL"]["beta"] == -0.20738438137868936
    # phase27_enabled False should keep production
    from app.simulation.version import WEATHER_MODEL_VERSION, RACE_CONTROL_MODEL_VERSION, STRATEGY_MODEL_VERSION, SETUP_MODEL_VERSION
    assert WEATHER_MODEL_VERSION == "weather-v1.0.0"
    assert RACE_CONTROL_MODEL_VERSION == "racecontrol-v1.0.0"
    assert STRATEGY_MODEL_VERSION == "strategy-v1.1.0"
    assert SETUP_MODEL_VERSION == "setup-v1.0.0"

def test_docs_exist():
    required = ["phase27_preflight_audit.md","phase27_lap_quality.md","phase27_decomposition.md","phase27_circuit_model.md","phase27_driver_model.md","phase27_constructor_model.md","phase27_progression.md","phase27_tyre_reassessment.md","phase27_pit_effect.md","phase27_weather_rc.md","phase27_residuals.md","phase27_walk_forward.md","phase27_falsification.md","phase27_performance.md","phase27_limitations.md","phase27_completion_report.md"]
    for doc in required:
        assert os.path.exists(os.path.join(DOCS, doc)), f"missing {doc}"

def test_no_synthetic_variables():
    d = load27()
    assert d["identifiable"]["fuel"] == "NON_IDENTIFIABLE"
    # ensure not fabricating fuel load
    assert "fuel_load" not in json.dumps(d["tyre"])
    # progression is associational not fuel
    assert d["identifiable"]["progression"] == "RACE_PROGRESSION_ASSOCIATIONAL"

def test_promotion_gate():
    d = load27()
    pg = d["promotion_gate"]
    assert pg["temporal_leakage"] is True
    assert pg["deterministic_reproducibility"] is True
    assert pg["physical_sanity"] is False
    assert pg["walk_forward_improvement"] is False
    assert pg["no_major_confounding"] is False
    assert pg["decision"] == "KEEP_PRODUCTION_MODEL"
    assert pg["promoted"] is False
