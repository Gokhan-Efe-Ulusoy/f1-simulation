import time, json, pathlib, hashlib, sys, platform, os
sys.path.insert(0, "backend")
from app.simulation.race_engine_v14 import RaceEngine as Ref
from app.simulation.race_engine_v15 import RaceEngineV15 as Opt
from app.simulation.scenario_v14 import ScenarioResolver
from app.data.scenario import build_scenario

from pathlib import Path
_data_root = Path(__file__).parent.parent / "data"
races=json.loads(open(_data_root / "canonical" / "races.json").read())
race=[r for r in races if r["race_id"]=="2024-bahrain"][0]
results=json.loads(open(_data_root / "canonical" / "results.json").read())
race_results=[res for res in results if res["race_id"]==race["race_id"]]
hist=build_scenario(race, race_results)
scenario=ScenarioResolver.from_historical(hist, race_date=race["date"])
scenario.race_distance["laps"]=58

def fp(res):
    parts=[]
    for did in sorted(res["drivers"].keys()):
        parts.append(f"{did}:{res['drivers'][did]['win_probability']:.6f}:{res['drivers'][did]['podium_probability']:.6f}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]

# Test 10k
for n in [10000]:
    ref=Ref(seed=42)
    s=time.perf_counter()
    r1=ref.simulate(scenario, simulations=n, seed=42)
    t1=time.perf_counter()-s
    print(f"Ref {n} laps 58: {t1:.3f}s ({n/t1:.1f}/s)")
    opt=Opt(seed=42)
    s=time.perf_counter()
    r2=opt.simulate(scenario, simulations=n, seed=42)
    t2=time.perf_counter()-s
    print(f"Opt {n} laps 58: {t2:.3f}s ({n/t2:.1f}/s) speedup {t1/t2:.2f}x")
    print(f"fp ref {fp(r1)} opt {fp(r2)}")
    # Check win sum
    win_sum_ref=sum(v["win_probability"] for v in r1["drivers"].values())
    win_sum_opt=sum(v["win_probability"] for v in r2["drivers"].values())
    print(f"win sum ref {win_sum_ref:.4f} opt {win_sum_opt:.4f}")
    # Check top driver
    top_ref=max(r1["drivers"].items(), key=lambda x: x[1]["win_probability"])
    top_opt=max(r2["drivers"].items(), key=lambda x: x[1]["win_probability"])
    print(f"top ref {top_ref[0]} {top_ref[1]['win_probability']:.3f} vs opt {top_opt[0]} {top_opt[1]['win_probability']:.3f}")

# Also test 5 laps 10k
scenario.race_distance["laps"]=5
for n in [10000]:
    ref=Ref(seed=42)
    s=time.perf_counter()
    r1=ref.simulate(scenario, simulations=n, seed=42)
    t1=time.perf_counter()-s
    opt=Opt(seed=42)
    s=time.perf_counter()
    r2=opt.simulate(scenario, simulations=n, seed=42)
    t2=time.perf_counter()-s
    print(f"5 laps Ref {n}: {t1:.3f}s Opt {t2:.3f}s speedup {t1/t2:.2f}x")
