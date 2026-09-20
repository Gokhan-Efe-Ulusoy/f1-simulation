"""Phase 22 e2e experiment 2 — front-wing setup counterfactual, 2024 Bahrain.

Baseline: neutral Phase 20 setup (historical setups unknown).
Counterfactual: front_wing_angle +2 for the target driver (5.0 -> 7.0).
Sensitivity: OFAT front_wing [3, 4, 5, 6, 7].
Usage: python scripts/phase22_experiment_setup.py [--n 1000]
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

DID = "max-verstappen"

QUESTION = (
    "Under the model assumptions and available evidence, how does the "
    "simulated finish distribution change when max-verstappen's front wing "
    "angle rises by 2 degrees (5.0 -> 7.0)? Setup coefficients are "
    "PRIOR_ONLY; historical setups are NON_IDENTIFIABLE."
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
        [Intervention(family="setup", op="SET_VALUE", target=DID,
                      parameter="front_wing", value=7.0)],
        experiment_id=f"exp-2024-bahrain-frontwing-plus2-n{n}",
        question=QUESTION,
    )
    t_legs = time.perf_counter() - t0

    seng = SensitivityEngine(seed=42, simulations=n)
    hrace = eng.load_race("2024-bahrain")
    base = eng.scenario_for_race(hrace)
    t1 = time.perf_counter()
    sens = seng.run_ofat(
        base, f"exp-2024-bahrain-frontwing-plus2-n{n}-sens",
        family="setup", target=DID, parameter="front_wing",
        values=[3.0, 4.0, 5.0, 6.0, 7.0],
    )
    t_sens = time.perf_counter() - t1
    exp.sensitivity = sens
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    path = save_experiment(exp, slug="frontwing-plus2")
    report = save_markdown_report(exp, name="experiment_2024_bahrain_setup_frontwing")
    offs = (exp.comparison.race_effects.get("setup", {}) or {}).get("counterfactual", {})
    print(json.dumps({
        "experiment_id": exp.experiment_id,
        "fingerprint": exp.fingerprint,
        "n": n,
        "legs_time_s": round(t_legs, 1),
        "sens_time_s": round(t_sens, 1),
        "peak_python_mem_mb": round(peak / 1e6, 1),
        "setup_offset_target_s_per_lap": offs.get(DID),
        "sens_points": [
            {"value": p.value, "d_win": round(p.d_win_probability, 4),
             "d_finish": round(p.d_expected_finish, 3),
             "l1": round(p.l1_finish_distribution, 4)} for p in sens.points
        ],
        "artifact": str(path),
        "report": str(report),
    }, indent=1))


if __name__ == "__main__":
    main()
