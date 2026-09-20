"""Phase 22 e2e experiment 3 — wet-weather counterfactual, 2024 Bahrain.

Baseline: dry model prior (historical weather NON_IDENTIFIABLE).
Counterfactual: rainfall_mm_h 0 -> 10 (earlier/stronger rain proxy; the model
supports initial-state overrides only, not timed onset scripting).
Sensitivity: OFAT rainfall [0, 5, 10, 15, 20].
Usage: python scripts/phase22_experiment_weather.py [--n 1000]
"""
import argparse
import json
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.simulation.replay.artifacts import save_experiment, save_markdown_report
from app.simulation.replay.replay_engine import ReplayEngine
from app.simulation.replay.sensitivity import SensitivityEngine
from app.simulation.scenario.models import Intervention

QUESTION = (
    "Under the model assumptions and available evidence, how does the "
    "simulated finish distribution change when the race starts wet "
    "(rainfall 10 mm/h) instead of dry? Historical weather is "
    "NON_IDENTIFIABLE; timed rain onset is NOT_TESTABLE in this model."
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    args = ap.parse_args()
    n = int(args.n)

    eng = ReplayEngine(seed=42, simulations=n)
    t0 = time.perf_counter()
    tracemalloc.start()
    exp = eng.counterfactual(
        "2024-bahrain",
        [Intervention(family="weather", op="SET_VALUE", target="race",
                      parameter="rainfall_mm_h", value=10.0)],
        experiment_id=f"exp-2024-bahrain-wet-rain10-n{n}",
        question=QUESTION,
    )
    t_legs = time.perf_counter() - t0

    seng = SensitivityEngine(seed=42, simulations=n)
    hrace = eng.load_race("2024-bahrain")
    base = eng.scenario_for_race(hrace)
    t1 = time.perf_counter()
    sens = seng.run_ofat(
        base, f"exp-2024-bahrain-wet-rain10-n{n}-sens",
        family="weather", target="race", parameter="rainfall_mm_h",
        values=[0.0, 5.0, 10.0, 15.0, 20.0],
    )
    t_sens = time.perf_counter() - t1
    exp.sensitivity = sens
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    path = save_experiment(exp, slug="wet-rain10")
    report = save_markdown_report(exp, name="experiment_2024_bahrain_weather_wet")
    wx = exp.comparison.race_effects.get("weather", {})
    print(json.dumps({
        "experiment_id": exp.experiment_id,
        "fingerprint": exp.fingerprint,
        "n": n,
        "legs_time_s": round(t_legs, 1),
        "sens_time_s": round(t_sens, 1),
        "peak_python_mem_mb": round(peak / 1e6, 1),
        "weather_delta": (wx.get("delta", {}) if isinstance(wx, dict) else {}),
        "sens_points": [
            {"value": p.value, "d_win": round(p.d_win_probability, 4),
             "l1": round(p.l1_finish_distribution, 4)} for p in sens.points
        ],
        "artifact": str(path),
        "report": str(report),
    }, indent=1))


if __name__ == "__main__":
    main()
