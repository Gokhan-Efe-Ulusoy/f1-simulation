"""Phase 23 calibration validation (offline)."""
import json, os, glob, hashlib
import pytest
import pyarrow.parquet as pq

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALIB=os.path.join(ROOT,"data","calibration","phase23")

def test_mart_exists_and_reproducible():
    assert os.path.exists(os.path.join(CALIB,"mart_manifest.json"))
    with open(os.path.join(CALIB,"mart_manifest.json")) as h:
        m=json.load(h)
    assert m["dataset_id"]=="f1-dataset-v1.3"
    assert m["reproducible"] is True
    assert m["temporal_policy"]=="strict_before_as_of"

def test_mart_schema():
    for tbl in ["lap_mart.parquet","stint_mart.parquet","pit_mart.parquet","race_mart.parquet"]:
        assert os.path.exists(os.path.join(CALIB,tbl))
        meta=pq.ParquetFile(os.path.join(CALIB,tbl)).metadata
        assert meta.num_rows>0

def test_mart_provenance():
    for tbl in ["lap_mart.parquet"]:
        rows=pq.ParquetFile(os.path.join(CALIB,tbl)).read(columns=["race_id","season","as_of"]).to_pylist()
        assert all(r["race_id"] and r["as_of"] for r in rows[:10])

def test_temporal_filtering():
    # training observations must be < target date
    with open(os.path.join(CALIB,"leakage_report.json")) as h:
        data=json.load(h)
    assert data["violations"]==0

def test_leakage_adversarial():
    with open(os.path.join(CALIB,"leakage_report.json")) as h:
        data=json.load(h)
    assert data["adversarial_tests"]>=6
    assert data["passed"]==data["adversarial_tests"]

def test_missingness_preserved():
    # stint tyre missing should not be fabricated
    with open(os.path.join(CALIB,"tyre_calibration.json")) as h:
        tyre=json.load(h)
    assert tyre["historical"]["status"]=="NON_IDENTIFIABLE"

def test_duplicate_handling():
    # lap mart should have same PK uniqueness as canonical
    rows=pq.ParquetFile(os.path.join(CALIB,"lap_mart.parquet")).read(columns=["race_id","driver_ref","lap_number"]).to_pylist()
    ids=[f"{r['race_id']}:{r['driver_ref']}:{r['lap_number']}" for r in rows[:1000]]
    assert len(ids)==len(set(ids))

def test_driver_resolution():
    with open(os.path.join(CALIB,"driver_model.json")) as h:
        dm=json.load(h)
    assert dm["STATUS"] in ("LIMITED","CALIBRATED","PRIOR_ONLY")
    # ensure shrinkage exists
    sample=list(dm["estimates"].values())[0]
    assert "shrunk" in sample and "se" in sample

def test_constructor_resolution():
    with open(os.path.join(CALIB,"constructor_model.json")) as h:
        m=json.load(h)
    assert m["STATUS"] in ("LIMITED","CALIBRATED","PRIOR_ONLY","NON_IDENTIFIABLE")

def test_circuit_resolution():
    with open(os.path.join(CALIB,"circuit_model.json")) as h:
        m=json.load(h)
    assert m["STATUS"] in ("LIMITED","CALIBRATED")
    assert len(m["effects"])>10

def test_tyre_calibration():
    with open(os.path.join(CALIB,"tyre_calibration.json")) as h:
        tyre=json.load(h)
    for comp in ["soft","medium","hard"]:
        assert tyre[comp]["evidence_tier"] in ("LIMITED","PRIOR_ONLY","CALIBRATED")
        assert tyre[comp]["n_stints"]>=0

def test_pit_calibration():
    with open(os.path.join(CALIB,"pit_calibration.json")) as h:
        pit=json.load(h)
    assert pit["STATUS"] in ("CALIBRATED","LIMITED")
    assert pit["n"]>500
    assert pit["mean"]>15 and pit["mean"]<40

def test_progression_fuel_identifiability():
    with open(os.path.join(CALIB,"fuel_model.json")) as h:
        fuel=json.load(h)
    assert fuel["STATUS"]=="NON_IDENTIFIABLE"
    assert fuel["IDENTIFIABILITY"]=="NON_IDENTIFIABLE"
    assert "progression_slope" in fuel

def test_driver_model_shrinkage():
    with open(os.path.join(CALIB,"driver_model.json")) as h:
        dm=json.load(h)
    for drv, est in list(dm["estimates"].items())[:5]:
        assert abs(est["shrunk"]) <= abs(est["raw"]) + 1e-9

def test_constructor_model():
    with open(os.path.join(CALIB,"constructor_model.json")) as h:
        m=json.load(h)
    assert "method" in m

def test_circuit_model_shrinkage():
    with open(os.path.join(CALIB,"circuit_model.json")) as h:
        m=json.load(h)
    for c, est in list(m["effects"].items())[:3]:
        assert abs(est["shrunk"]) <= abs(est["raw"]) + 1e-9

def test_era_model():
    with open(os.path.join(CALIB,"era_model.json")) as h:
        m=json.load(h)
    assert m["STATUS"]=="CALIBRATED"
    assert len(m["eras"])>=5

def test_uncertainty_reported():
    with open(os.path.join(CALIB,"uncertainty.json")) as h:
        u=json.load(h)
    assert "tyre_se_per_compound" in u
    assert "pit_se" in u

def test_shrinkage():
    # ensure sparse drivers have larger se
    with open(os.path.join(CALIB,"driver_model.json")) as h:
        dm=json.load(h)
    sparse=[v for v in dm["estimates"].values() if v["n"]<5]
    dense=[v for v in dm["estimates"].values() if v["n"]>50]
    if sparse and dense:
        assert statistics.mean([s["se"] for s in sparse]) > statistics.mean([d["se"] for d in dense])

def test_walk_forward():
    with open(os.path.join(CALIB,"walk_forward.json")) as h:
        wf=json.load(h)
    assert len(wf["splits"])>=5
    for sp in wf["splits"]:
        assert sp["metrics"] is not None
        assert sp["metrics"]["mae"]>0

def test_ablation():
    with open(os.path.join(CALIB,"ablation.json")) as h:
        ab=json.load(h)
    assert len(ab)>=5
    for k,v in ab.items():
        assert "decision" in v

def test_falsification():
    with open(os.path.join(CALIB,"falsification.json")) as h:
        fal=json.load(h)
    assert all(v["passed"] for v in fal.values())
    assert len(fal)>=5

def test_counterfactual_sanity():
    with open(os.path.join(CALIB,"counterfactual.json")) as h:
        cf=json.load(h)
    assert all(v["passed"] for v in cf.values())

def test_deterministic_calibration():
    import hashlib, json as js
    with open(os.path.join(CALIB,"reproducibility.json")) as h:
        repro=json.load(h)
    assert repro["same_input_same_output"] is True
    assert repro["seed"]==42

def test_hash_stability():
    with open(os.path.join(ROOT,"data","manifests","phase23_calibration_manifest.json")) as h:
        m=json.load(h)
    assert m["reproducible"] is True
    assert len(m["artifacts"])>=3

def test_promotion_gates():
    with open(os.path.join(CALIB,"promotion_gates.json")) as h:
        gates=json.load(h)
    assert "CALIBRATED" in gates
    assert gates["gates"]["fuel"]["decision"]=="NON_IDENTIFIABLE"
    assert gates["gates"]["pit_total"]["decision"]=="CALIBRATED"

def test_regression_no_model_drift():
    with open(os.path.join(ROOT,"data","manifests","registry.json")) as h:
        reg=json.load(h)
    ids=[e["dataset_id"] for e in reg]
    assert "f1-dataset-v1.3" in ids
    # ensure v1.0 not overwritten
    for expected in ["calibration-v1.0.0","tyre-calibration-v1.0.0","raceengine-v1.2.0"]:
        assert expected in ids

def test_performance():
    with open(os.path.join(CALIB,"performance.json")) as h:
        perf=json.load(h)
    assert perf["memory_mb"]<1000
    assert "calibration_runtime_s" in perf

def test_no_fabricated_compounds():
    with open(os.path.join(CALIB,"tyre_calibration.json")) as h:
        tyre=json.load(h)
    assert tyre["historical"]["status"] in ("NON_IDENTIFIABLE","PRIOR_ONLY")

def test_evidence_tier_requirements():
    with open(os.path.join(CALIB,"promotion_gates.json")) as h:
        gates=json.load(h)
    # fuel should be NON_IDENTIFIABLE, not CALIBRATED
    assert gates["gates"]["fuel"]["decision"] != "CALIBRATED"
    assert gates["gates"]["setup"]["decision"]=="NON_IDENTIFIABLE"

def test_reproducibility_manifest():
    assert os.path.exists(os.path.join(ROOT,"data","manifests","phase23_calibration_manifest.json"))
    with open(os.path.join(ROOT,"data","manifests","phase23_calibration_manifest.json")) as h:
        m=json.load(h)
    assert m["leakage_violations"]==0
    assert m["dataset_id"]=="f1-dataset-v1.3"

import statistics
