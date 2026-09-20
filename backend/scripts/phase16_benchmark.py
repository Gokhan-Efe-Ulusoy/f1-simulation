"""Phase 16 benchmark — tyre-enabled vs baseline, 10k x 58 laps."""
import time, json, pathlib, sys
sys.path.insert(0, "backend")
from pathlib import Path
from app.simulation.race_engine_v15 import RaceEngineV15
from app.simulation.race_engine_v16 import TyreAwareRaceEngine
from app.simulation.scenario_v14 import ScenarioResolver
from app.data.scenario import build_scenario

_data_root = Path(__file__).parent.parent / "data"
races=json.loads(open(_data_root / "canonical" / "races.json").read())
race=[r for r in races if r["race_id"]=="2024-bahrain"][0]
results=json.loads(open(_data_root / "canonical" / "results.json").read())
race_results=[res for res in results if res["race_id"]==race["race_id"]]
hist=build_scenario(race, race_results)
scenario=ScenarioResolver.from_historical(hist, race_date=race["date"])

for laps in [5, 58]:
    scenario.race_distance["laps"]=laps
    print(f"\n=== Laps {laps} ===")
    for n in [1000, 10000]:
        # Baseline (no tyre)
        base=RaceEngineV15(seed=42)
        s=time.perf_counter()
        r1=base.simulate(scenario, simulations=n, seed=42)
        t1=time.perf_counter()-s
        # Tyre-enabled
        tyre=TyreAwareRaceEngine(seed=42, tyre_enabled=True)
        s=time.perf_counter()
        r2=tyre.simulate(scenario, simulations=n, seed=42)
        t2=time.perf_counter()-s
        print(f"N={n}: baseline {t1:.3f}s ({n/t1:.0f}/s) tyre {t2:.3f}s ({n/t2:.0f}/s) speedup {t1/t2:.2f}x")
        # Check win prob diff
        top1=max(r1["drivers"].items(), key=lambda x: x[1]["win_probability"])
        top2=max(r2["drivers"].items(), key=lambda x: x[1]["win_probability"])
        print(f"  baseline top {top1[0]} {top1[1]['win_probability']:.3f} vs tyre {top2[0]} {top2[1]['win_probability']:.3f}")

# Save results
out=_data_root / "simulation" / "benchmarks" / "phase16_benchmark.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"note": "Phase 16 tyre benchmark, see console"}, indent=2))
print(f"Saved to {out}")
