"""Phase 16.6 reproducibility tests."""
import json, pathlib, hashlib
from pathlib import Path

import pytest

pytestmark = pytest.mark.reproducibility


ROOT=Path(__file__).parent.parent
DATA_ROOT=ROOT / "data"

def test_same_seed_deterministic():
    from app.simulation.race_engine_v15 import RaceEngineV15
    from app.simulation.scenario_v14 import ScenarioResolver
    from app.data.scenario import build_scenario
    races=json.loads((DATA_ROOT/"canonical"/"races.json").read_text())
    race=[r for r in races if r["race_id"]=="2024-bahrain"][0]
    results=json.loads((DATA_ROOT/"canonical"/"results.json").read_text())
    race_results=[res for res in results if res["race_id"]==race["race_id"]]
    hist=build_scenario(race, race_results)
    scenario=ScenarioResolver.from_historical(hist, race_date=race["date"])
    scenario.race_distance["laps"]=5
    engine=RaceEngineV15(seed=42)
    r1=engine.simulate(scenario, simulations=20, seed=42)
    r2=engine.simulate(scenario, simulations=20, seed=42)
    assert r1["drivers"]==r2["drivers"]

def test_reference_optimized_rng_equality():
    from app.simulation.race_engine_v14 import RaceEngine as Ref
    from app.simulation.race_engine_v15 import RaceEngineV15 as Opt
    from app.simulation.scenario_v14 import ScenarioResolver
    from app.data.scenario import build_scenario
    races=json.loads((DATA_ROOT/"canonical"/"races.json").read_text())
    race=[r for r in races if r["race_id"]=="2024-bahrain"][0]
    results=json.loads((DATA_ROOT/"canonical"/"results.json").read_text())
    race_results=[res for res in results if res["race_id"]==race["race_id"]]
    hist=build_scenario(race, race_results)
    scenario=ScenarioResolver.from_historical(hist, race_date=race["date"])
    scenario.race_distance["laps"]=5
    ref=Ref(seed=42)
    opt=Opt(seed=42)
    r1=ref.simulate(scenario, simulations=10, seed=42)
    r2=opt.simulate(scenario, simulations=10, seed=42)
    # For N=10, should be exact
    for did in r1["drivers"]:
        assert abs(r1["drivers"][did]["win_probability"]-r2["drivers"][did]["win_probability"]) < 0.01

def test_ar1_stream():
    from app.simulation.performance.numerical_kernels import ar1_step
    import numpy as np
    noise=np.zeros((2,3))
    rand=np.ones((2,3))*0.4
    out=ar1_step(noise, rand, coeff=0.7)
    # With zero noise, out should be rand
    assert (out==rand).all()

def test_batch_invariance():
    """Exact determinism for repeated identical calls (Phase 33 revision).

    NOTE (Phase 33 audit A3): this test previously asserted that the argmax
    driver of an N=10 run equals the argmax of an N=100 run with the same
    seed. That property is NOT guaranteed by design: with CRN the first 10
    draws coincide, but win_probability quantisation (0.1 vs 0.01 steps)
    lets the argmax legitimately differ — sampling noise, not
    nondeterminism. Asserting cross-N argmax equality therefore failed
    deterministically and could never be fixed by engine changes.
    The assertions below test the actual guarantee — bit-identical output
    for identical inputs — twice (small-N and larger-N).
    """
    from app.simulation.race_engine_v15 import RaceEngineV15
    from app.simulation.scenario_v14 import ScenarioResolver
    from app.data.scenario import build_scenario
    races=json.loads((DATA_ROOT/"canonical"/"races.json").read_text())
    race=[r for r in races if r["race_id"]=="2024-bahrain"][0]
    results=json.loads((DATA_ROOT/"canonical"/"results.json").read_text())
    race_results=[res for res in results if res["race_id"]==race["race_id"]]
    hist=build_scenario(race, race_results)
    scenario=ScenarioResolver.from_historical(hist, race_date=race["date"])
    scenario.race_distance["laps"]=5
    engine=RaceEngineV15(seed=42)
    r1=engine.simulate(scenario, simulations=10, seed=42)
    r1b=engine.simulate(scenario, simulations=10, seed=42)
    assert r1["drivers"]==r1b["drivers"]
    r2=engine.simulate(scenario, simulations=100, seed=42)
    r2b=engine.simulate(scenario, simulations=100, seed=42)
    assert r2["drivers"]==r2b["drivers"]

def test_cache_invariance():
    from app.data.calibration_api import _load_json, _clear_cache
    from pathlib import Path
    _clear_cache()
    p=Path("data/calibration/models/driver_model.json")
    # Cold
    d1=_load_json(p)
    # Warm
    d2=_load_json(p)
    assert d1==d2
    _clear_cache()
    d3=_load_json(p)
    assert d1==d3

def test_fingerprint():
    import hashlib, json
    races=json.loads((DATA_ROOT/"canonical"/"races.json").read_text())
    race=[r for r in races if r["race_id"]=="2024-bahrain"][0]
    # Simple fingerprint of race
    raw=json.dumps(race, sort_keys=True).encode()
    h1=hashlib.sha256(raw).hexdigest()[:8]
    h2=hashlib.sha256(raw).hexdigest()[:8]
    assert h1==h2
    # Different race should give different
    race2=[r for r in races if r["race_id"]=="2024-jeddah"][0]
    raw2=json.dumps(race2, sort_keys=True).encode()
    h3=hashlib.sha256(raw2).hexdigest()[:8]
    assert h1!=h3
