"""Phase 15 benchmark — baseline and optimized, reproducible."""
import json, time, platform, sys, hashlib, os
from pathlib import Path
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent))

from app.simulation.race_engine_v14 import RaceEngine
from app.simulation.scenario_v14 import ScenarioResolver
from app.data.scenario import build_scenario
import json as _json

ROOT = Path(__file__).parent.parent
DATA_ROOT = ROOT / "data"

def get_env():
    import numpy
    env={}
    env["python"] = platform.python_version()
    env["platform"] = platform.platform()
    env["cpu"] = platform.processor()
    try:
        env["cpu_count"] = os.cpu_count()
    except: env["cpu_count"] = None
    try:
        import psutil
        env["ram_gb"] = round(psutil.virtual_memory().total / 1024**3, 2)
    except: env["ram_gb"] = None
    env["numpy"] = numpy.__version__
    try:
        import numba
        env["numba"] = numba.__version__
    except: env["numba"] = None
    env["engine_version"] = "raceengine-v1.0.0"
    env["dataset_version"] = "f1-dataset-v1.1"
    env["calibration_version"] = "calibration-v1.0.0"
    return env

def fingerprint(result: dict) -> str:
    # Stable fingerprint: sorted win probs etc.
    parts=[]
    for did in sorted(result["drivers"].keys()):
        d=result["drivers"][did]
        parts.append(f"{did}:{d['win_probability']:.6f}:{d['podium_probability']:.6f}:{d['expected_finish']:.4f}")
    raw="|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def benchmark_one(scenario, simulations: int, seed=42):
    engine=RaceEngine(seed=seed)
    start=time.perf_counter()
    result=engine.simulate(scenario, simulations=simulations, seed=seed)
    elapsed=time.perf_counter()-start
    return result, elapsed

def main():
    # Load scenario 2024-bahrain
    races=json.loads((DATA_ROOT/"canonical"/"races.json").read_text())
    race=[r for r in races if r["race_id"]=="2024-bahrain"][0]
    results=json.loads((DATA_ROOT/"canonical"/"results.json").read_text())
    race_results=[res for res in results if res["race_id"]==race["race_id"]]
    hist=build_scenario(race, race_results)
    scenario=ScenarioResolver.from_historical(hist, race_date=race["date"])
    # For benchmark, use 5 laps to keep baseline measurable but also test 58 laps for final
    # We'll benchmark both: 5 laps for speed, and 58 laps for realistic
    # Use 5 laps for baseline matrix as per audit (20 drivers, 5 laps)
    scenario.race_distance["laps"]=5

    env=get_env()
    print(f"Env: {env}")

    counts=[10,100,500,1000,5000,10000]
    # For baseline, we will run up to 1000 only if 10k is too slow (>30s). We'll try.
    timings={}
    throughputs={}
    fingerprints={}

    for n in counts:
        # Skip 10k if previous 5000 took >30s to avoid timeout
        if n==10000 and timings.get("5000",0) > 60:
            print(f"Skipping {n} due to previous slow")
            timings[str(n)]=None
            continue
        print(f"Benchmark N={n} ...")
        result, elapsed=benchmark_one(scenario, simulations=n, seed=42)
        timings[str(n)]=elapsed
        throughputs[str(n)]=n/elapsed if elapsed>0 else 0
        fingerprints[str(n)]=fingerprint(result)
        print(f"  {n}: {elapsed:.3f}s, {n/elapsed:.1f} sims/s, fp {fingerprints[str(n)]}")
        # Save intermediate
        # Also store scientific fingerprint details
        # Save result summary for later validation
        out_path=DATA_ROOT / "simulation" / "benchmarks" / f"phase15_baseline_N{n}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({
            "n": n,
            "elapsed": elapsed,
            "throughput": n/elapsed if elapsed else 0,
            "fingerprint": fingerprints[str(n)],
            "win_prob_sample": {k: v["win_probability"] for k,v in list(result["drivers"].items())[:2]},
        }, indent=2))

    baseline={
        "phase": 15,
        "type": "baseline",
        "engine_version": env["engine_version"],
        "dataset_version": env["dataset_version"],
        "calibration_version": env["calibration_version"],
        "seed": 42,
        "scenario": "2024-bahrain",
        "driver_count": 20,
        "lap_count": 5,
        "simulation_counts": counts,
        "timings": timings,
        "throughput": throughputs,
        "scientific_fingerprint": fingerprints,
        "environment": env,
    }
    out=DATA_ROOT / "simulation" / "benchmarks" / "phase15_baseline.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(baseline, indent=2))
    print(f"Baseline saved to {out}")
    print(json.dumps(baseline, indent=2))

if __name__=="__main__":
    main()
