"""Phase 22 benchmark: replay + counterfactual + sensitivity at 58 laps.

Reports cold/warm wall time and peak Python memory for baseline, single
counterfactual, 5-point and 10-point OFAT sensitivity at N=1000/N=10000.
"""
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.simulation.replay.replay_engine import ReplayEngine
from app.simulation.replay.sensitivity import SensitivityEngine
from app.simulation.scenario.models import Intervention

DID = "max-verstappen"


def bench(n, sens_points):
    eng = ReplayEngine(seed=42, simulations=n)
    hrace = eng.load_race("2024-bahrain")
    base = eng.scenario_for_race(hrace)
    tracemalloc.start()
    t0 = time.perf_counter()
    rb = eng._simulate(base, n, 42)  # cold leg (incl. calibration/data load)
    t_cold = time.perf_counter() - t0
    t0 = time.perf_counter()
    rb2 = eng._simulate(eng.scenario_for_race(hrace), n, 42)  # warm leg
    t_warm = time.perf_counter() - t0
    t0 = time.perf_counter()
    exp = eng.counterfactual(
        "2024-bahrain",
        [Intervention(family="strategy", op="SET_VALUE", target=DID,
                      parameter="pit_laps", value=[25, 45])],
        experiment_id=f"bench-n{n}", laps=None,
    )
    t_cf = time.perf_counter() - t0
    seng = SensitivityEngine(seed=42, simulations=n)
    t0 = time.perf_counter()
    sens = seng.run_ofat(
        eng.scenario_for_race(hrace), f"bench-sens{n}",
        family="strategy", target=DID, parameter="pit_laps",
        values=[[20 + 2 * i, 40 + 2 * i] for i in range(sens_points - 1)] + [[38, 56]],
    )
    t_sens = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"N={n}: cold_leg={t_cold:.1f}s warm_leg={t_warm:.1f}s "
          f"counterfactual(both legs)={t_cf:.1f}s "
          f"sens{len(sens.points)}={t_sens:.1f}s "
          f"peak_python_mem={peak / 1e6:.1f}MB "
          f"sims_per_sec={n / max(t_warm, 1e-9):.0f}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--points", type=int, default=5)
    args = ap.parse_args()
    bench(int(args.n), int(args.points))
