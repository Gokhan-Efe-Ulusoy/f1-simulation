"""Profile hot paths for Phase 15."""
import cProfile, pstats, io, time, json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.simulation.race_engine_v14 import RaceEngine
from app.simulation.scenario_v14 import ScenarioResolver
from app.data.scenario import build_scenario

ROOT=Path(__file__).parent.parent

def profile_one():
    races=json.loads((ROOT/"data"/"canonical"/"races.json").read_text())
    race=[r for r in races if r["race_id"]=="2024-bahrain"][0]
    results=json.loads((ROOT/"data"/"canonical"/"results.json").read_text())
    race_results=[res for res in results if res["race_id"]==race["race_id"]]
    hist=build_scenario(race, race_results)
    scenario=ScenarioResolver.from_historical(hist, race_date=race["date"])
    scenario.race_distance["laps"]=58  # realistic

    engine=RaceEngine(seed=42)

    pr=cProfile.Profile()
    pr.enable()
    start=time.perf_counter()
    result=engine.simulate(scenario, simulations=200, seed=42)
    elapsed=time.perf_counter()-start
    pr.disable()

    s=io.StringIO()
    ps=pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(30)
    print(s.getvalue())
    print(f"Elapsed {elapsed:.3f}s for 200 sims, 58 laps, 20 drivers")

    # Save stats
    out=ROOT/"data"/"simulation"/"benchmarks"/"phase15_profile.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    # Extract top functions
    stats={}
    for func, (cc, nc, tt, ct, callers) in ps.stats.items():
        # func is (filename, lineno, func_name)
        key=f"{Path(func[0]).name}:{func[1]}:{func[2]}"
        stats[key]={"calls": cc, "total_time": tt, "cumulative": ct}
    # Sort by cumulative
    top=sorted(stats.items(), key=lambda x: x[1]["cumulative"], reverse=True)[:20]
    profile_data={
        "elapsed": elapsed,
        "simulations": 200,
        "laps": 58,
        "drivers": 20,
        "top_functions": [{"function": k, "calls": v["calls"], "total": v["total_time"], "cumulative": v["cumulative"]} for k,v in top],
        "raw": s.getvalue()[:5000],
    }
    out.write_text(json.dumps(profile_data, indent=2))
    print(f"Saved to {out}")

    # Also create markdown
    md=ROOT/"docs"/"phase15_profile.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md_content=f"""# Phase 15 Profile

**Scenario:** 2024-bahrain, 20 drivers, 58 laps, 200 simulations, seed 42
**Elapsed:** {elapsed:.3f}s
**Throughput:** {200/elapsed:.1f} sims/s

## Top 20 Functions by Cumulative Time

| Function | Calls | Total | Cumulative | % |
|---|---|---|---|---|
"""
    total=elapsed
    for k,v in top:
        pct=v["cumulative"]/total*100 if total else 0
        md_content+=f"| {k} | {v['calls']} | {v['total_time']:.4f} | {v['cumulative']:.4f} | {pct:.1f}% |\n"
    md_content+=f"\n## Analysis\n\nHot paths identified:\n"
    for k,v in top[:5]:
        md_content+=f"- {k}: {v['cumulative']:.3f}s ({v['cumulative']/total*100:.1f}%)\n"
    md.write_text(md_content)
    print(f"Markdown saved to {md}")

if __name__=="__main__":
    profile_one()
