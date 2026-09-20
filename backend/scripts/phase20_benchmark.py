"""Phase 20 benchmark: legacy vs setup-disabled vs setup-enabled."""
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

DATA_ROOT = pathlib.Path(__file__).parent.parent / "data"
races = json.loads((DATA_ROOT / "canonical" / "races.json").read_text())
race = [r for r in races if r["race_id"] == "2024-bahrain"][0]
results = json.loads((DATA_ROOT / "canonical" / "results.json").read_text())
race_results = [res for res in results if res["race_id"] == race["race_id"]]

from app.data.scenario import build_scenario
from app.simulation.scenario_v14 import ScenarioResolver
from app.simulation.race_engine_v19 import StrategyAwareRaceEngine as Legacy
from app.simulation.race_engine_v20 import SetupAwareRaceEngine as New

hist = build_scenario(race, race_results)


def make_scenario(mods, laps=8):
    s = ScenarioResolver.from_historical(hist, race_date=race["date"])
    s.race_distance["laps"] = laps
    s.hypothetical_modifiers = mods
    return s


configs = [
    ("legacy-v19", Legacy(seed=42), {"strategy": {"enabled": True}}),
    ("v20-disabled", New(seed=42), {"strategy": {"enabled": True}, "setup": {"enabled": False}}),
    ("v20-baseline", New(seed=42), {"strategy": {"enabled": True}, "setup": {"enabled": True}}),
]

N = 1000
print(f"Phase20 benchmark N={N} laps=8")
for label, eng, mods in configs:
    t0 = time.perf_counter()
    r = eng.simulate(make_scenario(mods), simulations=N, seed=42)
    dt = time.perf_counter() - t0
    sflag = r["provenance"].get("setup_enabled", "n/a")
    print(f"{label}: {dt:.2f}s sim_per_sec={N / dt:.0f} setup_enabled={sflag}")

# One modified-setup run to show offset cost is negligible
mods_mod = {
    "strategy": {"enabled": True},
    "setup": {"enabled": True, "mode": "counterfactual",
              "parameters": {"ride_height_front": 15.0, "ride_height_rear": 25.0}},
}
t0 = time.perf_counter()
r = New(seed=42).simulate(make_scenario(mods_mod), simulations=N, seed=42)
dt = time.perf_counter() - t0
print(f"v20-modified: {dt:.2f}s sim_per_sec={N / dt:.0f} offsets={r['setup_model']['offsets_sec_per_lap'] and 'nonzero' or 'zero'}")
