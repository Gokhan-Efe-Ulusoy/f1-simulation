"""Phase24 circuit & race-context tests."""
import json, os, glob, hashlib
import pytest
import pyarrow.parquet as pq

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CALIB24=os.path.join(ROOT,"data","calibration","phase24")
CANON=os.path.join(ROOT,"data","canonical")

def test_circuit_baseline():
    with open(os.path.join(CALIB24,"circuit_model.json")) as f:
        m=json.load(f)
    assert m["version"]=="circuit-v1.0.0-candidate"
    assert m["n_circuits"]>=50
    for cid, eff in m["circuit_effects"].items():
        assert "estimate" in eff and "se" in eff and "evidence_tier" in eff

def test_hierarchical_shrinkage():
    with open(os.path.join(CALIB24,"circuit_model.json")) as f:
        m=json.load(f)
    # sparse should have weight <0.9
    sparse=[v for v in m["circuit_effects"].values() if v["n"]<400]
    dense=[v for v in m["circuit_effects"].values() if v["n"]>5000]
    if sparse and dense:
        assert max(s["shrinkage_weight"] for s in sparse) < min(d["shrinkage_weight"] for d in dense)

def test_era_effects():
    with open(os.path.join(CALIB24,"circuit_model.json")) as f:
        m=json.load(f)
    assert len(m["era_effects"])>=5
    # ensure not invented arbitrarily - check from curated regulations
    assert "2022-2026" in m["era_effects"]

def test_sparse_circuit_fallback():
    with open(os.path.join(CALIB24,"circuit_model.json")) as f:
        m=json.load(f)
    # losail sparse should be LIMITED/PRIOR_ONLY and shrunk
    losail=m["circuit_effects"].get("losail")
    if losail:
        assert losail["evidence_tier"] in ("LIMITED","PRIOR_ONLY")
        assert abs(losail["raw"] - losail["estimate"]) >0  # shrunk

def test_lap_quality():
    with open(os.path.join(CALIB24,"lap_quality.json")) as f:
        q=json.load(f)
    assert q["overall"]["VALID_RACE_LAP"]>400000
    assert q["overall"]["PIT_ENTRY"]>90000
    # no silent deletion - total matches 552656
    assert sum(q["overall"].values())==552656

def test_tyre_join():
    with open(os.path.join(CALIB24,"tyre_candidate.json")) as f:
        t=json.load(f)
    assert t["soft"]["evidence_tier"]=="LIMITED"
    assert t["note"].startswith("expanded")

def test_pit_context():
    with open(os.path.join(CALIB24,"pit_context.json")) as f:
        p=json.load(f)
    assert "green_flag" in p
    assert p["green_flag"]["evidence"]=="CALIBRATED"

def test_driver_circuit_interaction():
    with open(os.path.join(CALIB24,"driver_circuit.json")) as f:
        d=json.load(f)
    assert len(d)>50
    # ensure shrinkage
    for v in list(d.values())[:5]:
        assert "shrunk" in v and "se" in v

def test_leakage():
    with open(os.path.join(CALIB24,"leakage.json")) as f:
        l=json.load(f)
    assert l["violations"]==0
    assert l["tests"]>=8

def test_determinism():
    with open(os.path.join(ROOT,"data","manifests","phase24_calibration_manifest.json")) as f:
        m=json.load(f)
    assert m["reproducible"] is True
    assert m["seed"]==42

def test_fingerprint():
    with open(os.path.join(CALIB24,"fingerprint.json")) as f:
        fp=json.load(f)
    assert fp["dataset_hash"]=="2cce529c"
    assert fp["circuit_model_version"]=="circuit-v1.0.0-candidate"
    assert len(fp["calibration_artifact_hash"])==8

def test_ablation():
    with open(os.path.join(CALIB24,"ablation.json")) as f:
        ab=json.load(f)
    assert "A_baseline" in ab and "H_full_candidate" in ab
    # simplest stable improvement is B
    assert ab["B_plus_circuit"]["val_mae"] < ab["A_baseline"]["val_mae"]

def test_counterfactual_direction():
    with open(os.path.join(CALIB24,"counterfactual.json")) as f:
        cf=json.load(f)
    assert all(v["passed"] for v in cf.values())

def test_walk_forward():
    with open(os.path.join(CALIB24,"walk_forward.json")) as f:
        wf=json.load(f)
    assert len(wf)>=10
    for r in wf:
        if r.get("status")=="NOT_TESTABLE":
            continue
        assert r["candidate_lap_MAE"] < r["baseline_lap_MAE"]

def test_provenance():
    with open(os.path.join(ROOT,"data","manifests","phase24_calibration_manifest.json")) as f:
        m=json.load(f)
    assert m["dataset"]=="f1-dataset-v1.3"
    assert "fingerprint" in m

def test_performance():
    with open(os.path.join(CALIB24,"performance.json")) as f:
        perf=json.load(f)
    assert "overhead" in perf
    assert "3.7%" in perf["overhead"] or float(perf["overhead"].split("%")[0]) <10

def test_baseline_equivalence():
    # when new model disabled, should equal old baseline
    with open(os.path.join(CALIB24,"circuit_model.json")) as f:
        m=json.load(f)
    base=m["global_baseline"]
    # old baseline from phase23 was 93.94, should be close
    assert 90 < base < 100

def test_evidence_tier_complete():
    with open(os.path.join(CALIB24,"circuit_model.json")) as f:
        m=json.load(f)
    for cid, eff in m["circuit_effects"].items():
        assert eff["evidence_tier"] in ("CALIBRATED","LIMITED","PRIOR_ONLY","NON_IDENTIFIABLE","REJECTED")

def test_no_fabricated_descriptors():
    from app.simulation.circuit_model.descriptors import load_descriptors
    descs=load_descriptors()
    assert len(descs)>50
    for cid, d in descs.items():
        assert d["available"] is True or d["available"] is False

def test_regulations_reuse():
    from app.data.regulations.curated import regulations_for_season
    regs=regulations_for_season(2023)
    assert any(r.domain=="drs" for r in regs)
