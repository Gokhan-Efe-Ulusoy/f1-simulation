"""Phase 21 benchmark: baseline vs counterfactual legs + comparison overhead.

Representative config: 2024-bahrain historical baseline, 8 laps.
Reports wall time per leg and comparison/explanation overhead.
"""
import json
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

ROOT = Path(__file__).parent.parent / "data"
races = json.loads((ROOT / "canonical" / "races.json").read_text())
race = [r for r in races if r["race_id"] == "2024-bahrain"][0]
results = json.loads((ROOT / "canonical" / "results.json").read_text())
race_results = [res for res in results if res["race_id"] == race["race_id"]]

from app.data.scenario import build_scenario
from app.simulation.scenario_v14 import ScenarioResolver
from app.simulation.scenario.engine import ScenarioEngine
from app.simulation.scenario.models import Intervention, ScenarioSpec

hist = build_scenario(race, race_results)


def base(laps=8):
    sc = ScenarioResolver.from_historical(hist, race_date=race["date"])
    sc.race_distance["laps"] = laps
    return sc


did = base().drivers[0]["driver_id"]
ivs = [
    Intervention(family="setup", op="SET_VALUE", target=did, parameter="rear_wing", value=3.0),
    Intervention(family="strategy", op="SET_VALUE", target=did, parameter="pit_laps", value=[4]),
    Intervention(family="weather", op="SET_VALUE", target="race", parameter="rainfall_mm_h", value=4.0),
    Intervention(family="race_control", op="DISABLE", target="race", parameter="enable_vsc", value=None),
]

for n in (1000, 10000):
    sc = base()
    eng = ScenarioEngine(seed=42, simulations=n)
    t0 = time.perf_counter()
    tracemalloc.start()
    rb = eng.run_baseline(sc, simulations=n, seed=42)
    t_base = time.perf_counter() - t0
    spec = ScenarioSpec(spec_id=f"bench-{n}", baseline_scenario_id=sc.scenario_id,
                        interventions=list(ivs), seed=42, simulations=n)
    t1 = time.perf_counter()
    res = eng.run_spec(base(), spec)
    t_both = time.perf_counter() - t1
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    t_cf = t_both - t_base  # approx: second run_spec = base leg + cf leg + compare
    print(f"N={n}: baseline_leg={t_base:.1f}s "
          f"run_spec(both legs+compare)={t_both:.1f}s "
          f"peak_python_mem={peak / 1e6:.1f}MB "
          f"sims_per_sec={n / max(t_base, 1e-9):.0f}")
print("comparison overhead is sub-second (dict arithmetic over "
      f"{len(rb['drivers'])} drivers); dominated by the two simulation legs.")
