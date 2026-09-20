"""RNG investigation for Phase 15 debt."""
import json, pathlib, sys
sys.path.insert(0, "backend")
from pathlib import Path
from app.simulation.race_engine_v14 import RaceEngine as Ref
from app.simulation.race_engine_v15 import RaceEngineV15 as Opt
from app.simulation.scenario_v14 import ScenarioResolver
from app.data.scenario import build_scenario

_data_root = Path("backend/data")
races=json.loads(open(_data_root / "canonical" / "races.json").read())
race=[r for r in races if r["race_id"]=="2024-bahrain"][0]
results=json.loads(open(_data_root / "canonical" / "results.json").read())
race_results=[res for res in results if res["race_id"]==race["race_id"]]
hist=build_scenario(race, race_results)
scenario=ScenarioResolver.from_historical(hist, race_date=race["date"])
scenario.race_distance["laps"]=5

# Test N=1 exact
for n in [1,2,10,100]:
    ref=Ref(seed=42)
    opt=Opt(seed=42)
    r1=ref.simulate(scenario, simulations=n, seed=42)
    r2=opt.simulate(scenario, simulations=n, seed=42)
    # Compare win probs
    diffs=[]
    for did in r1["drivers"]:
        diff=abs(r1["drivers"][did]["win_probability"]-r2["drivers"][did]["win_probability"])
        diffs.append(diff)
    max_diff=max(diffs) if diffs else 0
    print(f"N={n}: max win diff {max_diff:.4f}, top ref {max(r1['drivers'].items(), key=lambda x: x[1]['win_probability'])[0]} {max(r1['drivers'].items(), key=lambda x: x[1]['win_probability'])[1]['win_probability']:.3f} vs opt {max(r2['drivers'].items(), key=lambda x: x[1]['win_probability'])[0]} {max(r2['drivers'].items(), key=lambda x: x[1]['win_probability'])[1]['win_probability']:.3f}")

# Detailed trace for N=1
print("\n=== N=1 trace ===")
ref=Ref(seed=42)
opt=Opt(seed=42)
r1=ref.simulate(scenario, simulations=1, seed=42)
r2=opt.simulate(scenario, simulations=1, seed=42)
print("Ref drivers", {k: v["win_probability"] for k,v in list(r1["drivers"].items())[:3]})
print("Opt drivers", {k: v["win_probability"] for k,v in list(r2["drivers"].items())[:3]})
# Check if N=1 gives same finishing order (deterministic)
# For N=1, win prob is 0 or 1, so should be exact if RNG same
# Let's check finishing order for N=1
print("Ref win", max(r1["drivers"].items(), key=lambda x: x[1]["win_probability"])[0])
print("Opt win", max(r2["drivers"].items(), key=lambda x: x[1]["win_probability"])[0])

# Check RNG streams map
print("\n=== RNG Map ===")
print("Reference: seed+sim_idx*1000 per sim, per-driver Normal, per-lap AR1 with seed+100+lap")
print("Optimized: BatchRNG Level A for driver/constructor (seed+sim_idx*1000 per driver), Level B for lap noise (single RNG)")
print("Diff: lap noise Level B vs Level A causes win prob diff 0.20 for 10k")
