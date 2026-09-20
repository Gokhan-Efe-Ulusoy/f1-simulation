import time, json, pathlib, hashlib, sys
sys.path.insert(0, "backend")
from app.simulation.race_engine_v14 import RaceEngine as Ref
from app.simulation.race_engine_v15 import RaceEngineV15 as Opt
from app.simulation.scenario_v14 import ScenarioResolver
from app.data.scenario import build_scenario

races=json.loads(open('backend/data/canonical/races.json').read())
race=[r for r in races if r["race_id"]=="2024-bahrain"][0]
results=json.loads(open('backend/data/canonical/results.json').read())
race_results=[res for res in results if res["race_id"]==race["race_id"]]
hist=build_scenario(race, race_results)
scenario=ScenarioResolver.from_historical(hist, race_date=race["date"])

def fp(res):
    parts=[]
    for did in sorted(res["drivers"].keys()):
        parts.append(f"{did}:{res['drivers'][did]['win_probability']:.4f}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:8]

for laps in [5, 58]:
    scenario.race_distance["laps"]=laps
    print(f"\n=== Laps {laps} ===")
    for n in [10, 100, 500, 1000]:
        ref=Ref(seed=42)
        opt=Opt(seed=42)
        s=time.perf_counter()
        r1=ref.simulate(scenario, simulations=n, seed=42)
        t1=time.perf_counter()-s
        s=time.perf_counter()
        r2=opt.simulate(scenario, simulations=n, seed=42)
        t2=time.perf_counter()-s
        print(f"N={n:5d}: ref {t1:6.3f}s ({n/t1:7.1f}/s) opt {t2:6.3f}s ({n/t2:7.1f}/s) speedup {t1/t2:5.2f}x fp {fp(r1)} vs {fp(r2)}")
