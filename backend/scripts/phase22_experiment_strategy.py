"""Phase 22 e2e experiment 1 — pit-window shift (+5 laps), 2024 Bahrain.

Baseline: default strategy (model schedule, no pit-loss).
Counterfactual: target driver's pit laps shifted +5 (e.g. [20, 40] -> [25, 45]).
Usage: python scripts/phase22_experiment_strategy.py [--n 1000] [--sens 1]
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

DID = "max-verstappen"  # observed 2024-bahrain winner (validation target, not an input)
BASE_PITS = [20, 40]  # model default schedule at 58 laps (engine default; lap count NON_IDENTIFIABLE)
CF_PITS = [25, 45]

QUESTION = (
    "Under the model assumptions and available evidence, how does the "
    "simulated finish distribution for max-verstappen change when his pit "
    "window shifts +5 laps ([20, 40] -> [25, 45])?"
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--sens", type=int, default=1)
    args = ap.parse_args()

    n = int(args.n)
    eng = ReplayEngine(seed=42, simulations=n)
    t0 = time.perf_counter()
    tracemalloc.start()
    exp = eng.counterfactual(
        "2024-bahrain",
        [Intervention(family="strategy", op="SET_VALUE", target=DID,
                      parameter="pit_laps", value=list(CF_PITS))],
        experiment_id=f"exp-2024-bahrain-pit-shift5-n{n}",
        question=QUESTION,
    )
    t_legs = time.perf_counter() - t0

    sens = None
    if args.sens:
        seng = SensitivityEngine(seed=42, simulations=n)
        hrace = eng.load_race("2024-bahrain")
        base = eng.scenario_for_race(hrace)
        t1 = time.perf_counter()
        sens = seng.run_ofat(
            base, f"exp-2024-bahrain-pit-shift5-n{n}-sens",
            family="strategy", target=DID, parameter="pit_laps",
            values=[[20, 40], [22, 42], [25, 45], [28, 48], [30, 50]],
        )
        t_sens = time.perf_counter() - t1
        exp.sensitivity = sens
    else:
        t_sens = 0.0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    path = save_experiment(exp, slug="pitlap-shift5")
    report_name = ("experiment_2024_bahrain_pit_strategy" if n == 1000
                   else f"experiment_2024_bahrain_pit_strategy_n{n}")
    report = save_markdown_report(exp, name=report_name)
    ranked = sorted(exp.comparison.driver_deltas, key=lambda e: abs(e.d_win_probability), reverse=True)[:5]
    print(json.dumps({
        "experiment_id": exp.experiment_id,
        "fingerprint": exp.fingerprint,
        "n": n,
        "legs_time_s": round(t_legs, 1),
        "sens_time_s": round(t_sens, 1),
        "peak_python_mem_mb": round(peak / 1e6, 1),
        "top_deltas": [
            {"driver": e.driver_id, "d_win": round(e.d_win_probability, 4),
             "d_finish": round(e.d_expected_finish, 3),
             "l1": round(e.l1_finish_distribution, 4)} for e in ranked
        ],
        "artifact": str(path),
        "report": str(report),
    }, indent=1))


if __name__ == "__main__":
    main()
