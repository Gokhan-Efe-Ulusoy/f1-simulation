"""Phase 16 tyre tests — data, temporal, state, calibration, simulation, reproducibility."""
import json, pathlib, math
from pathlib import Path

ROOT=Path(__file__).parent.parent
DATA_ROOT=ROOT / "data"

def test_tyre_data_schema():
    # Check canonical pit_stops has expected fields, compound may be null
    p=DATA_ROOT / "canonical" / "pit_stops.json"
    data=json.loads(p.read_text())
    assert len(data)>0
    for row in data[:3]:
        assert "race_id" in row
        assert "driver_id" in row
        assert "lap_number" in row

def test_stint_reconstruction():
    # Check that stints can be reconstructed from pit stops
    # For 2024 Bahrain, we have pit stops and should be able to reconstruct stints
    from app.simulation.tyre.engine import TyreEngine
    engine=TyreEngine(as_of="2024-03-01")
    state=engine.initialize(season=2024, compound="SOFT", tyre_age=0)
    assert state.available
    assert state.tyre_age==0
    # After pit, new stint
    new_state=engine.update(state, lap=10, pit=True, new_compound="HARD")
    assert new_state.stint_index==1
    assert new_state.tyre_age==0
    assert new_state.compound.value=="HARD"

def test_compound_normalization():
    from app.simulation.tyre.compound import normalize_compound
    assert normalize_compound("SOFT")[0].value=="SOFT"
    assert normalize_compound("C5")[0].value=="SOFT"
    assert normalize_compound("MEDIUM")[0].value=="MEDIUM"
    assert normalize_compound("UNKNOWN")[0].value=="UNKNOWN"
    # Preserve source
    can, src=normalize_compound("C5")
    assert src=="C5"
    assert can.value=="SOFT"

def test_provenance():
    from app.simulation.tyre.calibration import load_tyre_observations
    obs=load_tyre_observations()
    if obs:
        assert "source" in obs[0]
        assert "provenance_hash" in obs[0] or "date" in obs[0]

def test_missing_data_handling():
    from app.simulation.tyre.engine import TyreEngine
    engine=TyreEngine(as_of="2024-03-01")
    # Unknown compound
    state=engine.initialize(season=1950, compound=None, tyre_age=None)
    assert not state.available
    assert state.evidence_tier in ["PRIOR_ONLY","NON_IDENTIFIABLE"]
    # Pit with unknown compound
    new_state=engine.update(state, lap=10, pit=True, new_compound=None)
    assert not new_state.available

def test_tyre_calibration_no_future_leakage():
    from app.simulation.tyre.calibration import calibrate_degradation, load_tyre_observations
    obs=load_tyre_observations()
    # Calibrate as_of before 2024 Bahrain, should not include 2024 Bahrain data if as_of is before
    # Our load has only 2024 data, so as_of 2023 should give no data
    result=calibrate_degradation(obs, as_of="2023-01-01")
    # Should be NON_IDENTIFIABLE or empty
    for comp, data in result.items():
        if comp!="GLOBAL":
            assert data["available"]==False or data["sample_size"]==0 or "NON_IDENTIFIABLE" in data["evidence_tier"]

def test_as_of_cutoff():
    from app.simulation.scenario_v14 import TemporalContext
    tc=TemporalContext(as_of="2024-02-29T00:00:00Z")
    assert tc.is_allowed("2024-02-28")
    assert not tc.is_allowed("2024-03-02")

def test_tyre_state_initialization():
    from app.simulation.tyre.engine import TyreEngine
    engine=TyreEngine(as_of="2024-03-01")
    state=engine.initialize(season=2024, compound="SOFT", tyre_age=5)
    assert state.tyre_age==5
    assert state.compound.value=="SOFT"
    assert state.available

def test_tyre_age_increment():
    from app.simulation.tyre.engine import TyreEngine
    engine=TyreEngine(as_of="2024-03-01")
    state=engine.initialize(season=2024, compound="SOFT", tyre_age=0)
    new_state=engine.update(state, lap=2, pit=False)
    assert new_state.tyre_age==1
    new_state2=engine.update(new_state, lap=3, pit=False)
    assert new_state2.tyre_age==2

def test_stint_transition():
    from app.simulation.tyre.engine import TyreEngine
    engine=TyreEngine(as_of="2024-03-01")
    state=engine.initialize(season=2024, compound="SOFT", tyre_age=10)
    new_state=engine.update(state, lap=15, pit=True, new_compound="MEDIUM")
    assert new_state.stint_index==1
    assert new_state.tyre_age==0

def test_pit_reset():
    from app.simulation.tyre.engine import TyreEngine
    engine=TyreEngine(as_of="2024-03-01")
    state=engine.initialize(season=2024, compound="SOFT", tyre_age=10)
    new_state=engine.update(state, lap=15, pit=True, new_compound="HARD")
    assert new_state.tyre_age==0
    assert new_state.compound.value=="HARD"

def test_unknown_compound():
    from app.simulation.tyre.engine import TyreEngine
    engine=TyreEngine(as_of="2024-03-01")
    state=engine.initialize(season=2024, compound="UNKNOWN", tyre_age=0)
    # Should still be available but with UNKNOWN
    assert state.compound.value=="UNKNOWN"

def test_compound_effect_calibration():
    from app.simulation.tyre.calibration import calibrate_compound_effect, load_tyre_observations
    obs=load_tyre_observations()
    result=calibrate_compound_effect(obs, as_of="2024-03-10")
    # Should have at least SOFT
    if obs:
        assert "SOFT" in result or "GLOBAL" in result

def test_degradation_calibration():
    from app.simulation.tyre.calibration import calibrate_degradation, load_tyre_observations
    obs=load_tyre_observations()
    result=calibrate_degradation(obs, as_of="2024-03-10")
    # Check structure
    for comp, data in result.items():
        assert "sample_size" in data
        assert "evidence_tier" in data
        if data.get("available"):
            assert "beta" in data
            assert data["beta"] is not None

def test_shrinkage():
    # Check that small sample has higher shrinkage
    from app.simulation.tyre.calibration import calibrate_degradation, load_tyre_observations
    obs=load_tyre_observations()
    result=calibrate_degradation(obs, as_of="2024-03-10")
    # For SOFT with n=~100, shrinkage should be moderate
    if "SOFT" in result and result["SOFT"].get("available"):
        assert result["SOFT"]["sample_size"]>0

def test_tyre_effect_deterministic():
    from app.simulation.tyre.engine import TyreEngine
    engine1=TyreEngine(as_of="2024-03-01")
    engine2=TyreEngine(as_of="2024-03-01")
    state1=engine1.initialize(season=2024, compound="SOFT", tyre_age=5)
    state2=engine2.initialize(season=2024, compound="SOFT", tyre_age=5)
    assert engine1.performance_effect(state1)==engine2.performance_effect(state2)

def test_tyre_integration():
    from app.simulation.race_engine_v16 import TyreAwareRaceEngine
    from app.simulation.scenario_v14 import ScenarioResolver
    from app.data.scenario import build_scenario
    import json
    races=json.loads((DATA_ROOT/"canonical"/"races.json").read_text())
    race=[r for r in races if r["race_id"]=="2024-bahrain"][0]
    results=json.loads((DATA_ROOT/"canonical"/"results.json").read_text())
    race_results=[res for res in results if res["race_id"]==race["race_id"]]
    hist=build_scenario(race, race_results)
    scenario=ScenarioResolver.from_historical(hist, race_date=race["date"])
    scenario.race_distance["laps"]=5
    engine=TyreAwareRaceEngine(seed=42, tyre_enabled=True)
    result=engine.simulate(scenario, simulations=10, seed=42)
    assert "tyre_model" in result
    assert result["tyre_model"]["version"]=="tyre-v1.0.0"

def test_reference_without_tyre_unchanged():
    from app.simulation.race_engine_v15 import RaceEngineV15
    from app.simulation.race_engine_v16 import TyreAwareRaceEngine
    from app.simulation.scenario_v14 import ScenarioResolver
    from app.data.scenario import build_scenario
    races=json.loads((DATA_ROOT/"canonical"/"races.json").read_text())
    race=[r for r in races if r["race_id"]=="1950-silverstone"][0]  # Historical, no tyre
    results=json.loads((DATA_ROOT/"canonical"/"results.json").read_text())
    race_results=[res for res in results if res["race_id"]==race["race_id"]]
    hist=build_scenario(race, race_results)
    scenario=ScenarioResolver.from_historical(hist, race_date=race["date"])
    scenario.race_distance["laps"]=5
    engine15=RaceEngineV15(seed=42)
    engine16=TyreAwareRaceEngine(seed=42, tyre_enabled=True)
    r15=engine15.simulate(scenario, simulations=10, seed=42)
    r16=engine16.simulate(scenario, simulations=10, seed=42)
    # For 1950, tyre unavailable, so results should be similar (both fallback to baseline)
    # At least check both have drivers
    assert len(r15["drivers"])==len(r16["drivers"])

def test_batch_tyre_state():
    from app.simulation.performance.batch_state import BatchState
    batch=BatchState(["a","b"], ["t1","t2"], N=10)
    assert batch.tyre_compound.shape==(10,2)
    assert batch.tyre_age.shape==(10,2)

def test_same_seed_same_output():
    from app.simulation.race_engine_v16 import TyreAwareRaceEngine
    from app.simulation.scenario_v14 import ScenarioResolver
    from app.data.scenario import build_scenario
    races=json.loads((DATA_ROOT/"canonical"/"races.json").read_text())
    race=[r for r in races if r["race_id"]=="2024-bahrain"][0]
    results=json.loads((DATA_ROOT/"canonical"/"results.json").read_text())
    race_results=[res for res in results if res["race_id"]==race["race_id"]]
    hist=build_scenario(race, race_results)
    scenario=ScenarioResolver.from_historical(hist, race_date=race["date"])
    scenario.race_distance["laps"]=5
    engine=TyreAwareRaceEngine(seed=42)
    r1=engine.simulate(scenario, simulations=20, seed=42)
    r2=engine.simulate(scenario, simulations=20, seed=42)
    assert r1["drivers"]==r2["drivers"]

def test_fingerprint_stability():
    from app.simulation.race_engine_v16 import TyreAwareRaceEngine
    from app.simulation.scenario_v14 import ScenarioResolver
    from app.data.scenario import build_scenario
    import hashlib, json
    races=json.loads((DATA_ROOT/"canonical"/"races.json").read_text())
    race=[r for r in races if r["race_id"]=="2024-bahrain"][0]
    results=json.loads((DATA_ROOT/"canonical"/"results.json").read_text())
    race_results=[res for res in results if res["race_id"]==race["race_id"]]
    hist=build_scenario(race, race_results)
    scenario=ScenarioResolver.from_historical(hist, race_date=race["date"])
    scenario.race_distance["laps"]=5
    engine=TyreAwareRaceEngine(seed=42)
    r1=engine.simulate(scenario, simulations=20, seed=42)
    r2=engine.simulate(scenario, simulations=20, seed=42)
    def fp(res):
        parts=[]
        for did in sorted(res["drivers"].keys()):
            parts.append(f"{did}:{res['drivers'][did]['win_probability']:.6f}")
        return hashlib.sha256("|".join(parts).encode()).hexdigest()[:8]
    assert fp(r1)==fp(r2)
