import json, sys
sys.path.insert(0, "backend")
from app.simulation.scenario_v14 import ScenarioResolver
from app.data.scenario import build_scenario
from app.simulation.calibration_state import build_calibration_state

races=json.loads(open('backend/data/canonical/races.json').read())
race=[r for r in races if r["race_id"]=="2024-bahrain"][0]
results=json.loads(open('backend/data/canonical/results.json').read())
race_results=[res for res in results if res["race_id"]==race["race_id"]]
hist=build_scenario(race, race_results)
scenario=ScenarioResolver.from_historical(hist, race_date=race["date"])
calib=build_calibration_state(scenario)
for did in ["max-verstappen","hamilton","leclerc","norris","russell"]:
    d=calib["drivers"].get(did, {})
    print(did, d.get("pace",{}).get("value"), d.get("pace",{}).get("uncertainty",{}).get("std"), d.get("sample_size"))
    c=calib["constructors"].get("red-bull" if did=="max-verstappen" else "mercedes" if did=="hamilton" else "ferrari" if did=="leclerc" else "mclaren" if did=="norris" else "mercedes")
    print("  constr", c.get("pace",{}).get("value") if c else None)
print("circuit", calib["circuit"])
