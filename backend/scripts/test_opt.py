from app.simulation.race_engine_v14 import RaceEngine as Ref
from app.simulation.race_engine_v15 import RaceEngineV15 as Opt
from app.simulation.scenario_v14 import ScenarioResolver
from app.data.scenario import build_scenario
import json, pathlib, time, hashlib

from pathlib import Path
_data_root = Path(__file__).parent.parent / "data"
races=json.loads(open(_data_root / "canonical" / "races.json").read())
race=[r for r in races if r["race_id"]=="2024-bahrain"][0]
results=json.loads(open(_data_root / "canonical" / "results.json").read())
race_results=[res for res in results if res["race_id"]==race["race_id"]]
hist=build_scenario(race, race_results)
scenario=ScenarioResolver.from_historical(hist, race_date=race["date"])
scenario.race_distance["laps"]=5
ref=Ref(seed=42)
opt=Opt(seed=42, use_vectorized=True)

s=time.perf_counter()
r1=ref.simulate(scenario, simulations=20, seed=42)
t1=time.perf_counter()-s
s=time.perf_counter()
r2=opt.simulate(scenario, simulations=20, seed=42)
t2=time.perf_counter()-s
print(f"Ref 20: {t1:.3f}s, Opt 20: {t2:.3f}s, speedup {t1/t2:.2f}x")

def fp(res):
    parts=[]
    for did in sorted(res["drivers"].keys()):
        d=res["drivers"][did]
        parts.append(f"{did}:{d['win_probability']:.4f}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:8]
print("ref fp", fp(r1))
print("opt fp", fp(r2))
for did in r1["drivers"]:
    diff=abs(r1["drivers"][did]["win_probability"]-r2["drivers"][did]["win_probability"])
    if diff>0.15:
        print(f"diff {did} {diff:.3f}")
        break
else:
    print("prob diff within tolerance")

# Test with 58 laps
scenario.race_distance["laps"]=58
s=time.perf_counter()
r1=ref.simulate(scenario, simulations=20, seed=42)
t1=time.perf_counter()-s
s=time.perf_counter()
r2=opt.simulate(scenario, simulations=20, seed=42)
t2=time.perf_counter()-s
print(f"58 laps Ref 20: {t1:.3f}s, Opt 20: {t2:.3f}s, speedup {t1/t2:.2f}x")
