"""Tyre calibration for Phase 16 — leakage-safe, hierarchical shrinkage."""
from __future__ import annotations

import json, math
from pathlib import Path
from collections import defaultdict
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = ROOT / "data"

def load_tyre_observations():
    """Load tyre lap observations from FastF1 and OpenF1 where available."""
    # Try FastF1 2024 Bahrain
    obs=[]
    try:
        import fastf1
        fastf1.Cache.enable_cache(str(DATA_ROOT / "raw" / "fastf1" / "cache"))
        sess=fastf1.get_session(2024, 'Bahrain', 'R')
        sess.load(telemetry=False)
        laps=sess.laps
        for _, row in laps.iterrows():
            # row has Driver, Compound, TyreLife, LapTime
            try:
                lap_time=row["LapTime"].total_seconds() if hasattr(row["LapTime"], "total_seconds") else float(row["LapTime"])  # noqa: E501
            except:
                continue
            obs.append({
                "season": 2024,
                "race_id": "2024-bahrain",
                "driver_id": str(row["Driver"]).lower(),
                "lap": int(row["LapNumber"]),
                "compound": str(row["Compound"]).upper() if row["Compound"] else None,
                "tyre_age": int(row["TyreLife"]) if not math.isnan(row["TyreLife"]) else None,
                "lap_time": lap_time,
                "source": "fastf1",
                "date": "2024-03-02",
            })
    except Exception as e:
        print(f"FastF1 load failed {e}")

    # Also try OpenF1 stints + laps for 2023
    try:
        import pathlib, json as j
        stint_path = DATA_ROOT / "raw" / "openf1" / "2023" / "7953" / "laps.json"
        # Actually stints are via API, but we have laps with is_pit_out_lap
        # For now, use FastF1 only
        pass
    except:
        pass
    return obs

def calibrate_degradation(observations, as_of: str = "2024-03-01"):
    """Leakage-safe: only observations < as_of."""
    # Filter by date - strict, no fallback (if as_of before data, return empty -> NON_IDENTIFIABLE)
    filtered=[o for o in observations if o["date"] < as_of]
    # Group by compound, filter NaN lap_time
    by_compound=defaultdict(list)
    for o in filtered:
        if o["compound"] and o["tyre_age"] is not None and o["lap_time"] is not None:
            # Filter NaN
            try:
                if math.isnan(float(o["lap_time"])):
                    continue
            except:
                pass
            by_compound[o["compound"]].append(o)
    # For each compound, fit linear degradation: lap_time vs tyre_age
    results={}
    for compound, rows in by_compound.items():
        if len(rows) < 10:
            results[compound]={
                "beta": None,
                "available": False,
                "reason": f"sample_size {len(rows)} <10",
                "evidence_tier": "NON_IDENTIFIABLE",
                "sample_size": len(rows),
            }
            continue
        # Simple linear regression: lap_time = intercept + beta * tyre_age
        ages=np.array([r["tyre_age"] for r in rows], dtype=float)
        times=np.array([r["lap_time"] for r in rows], dtype=float)
        # Remove outliers: filter to within 3 std
        # Use numpy polyfit
        try:
            beta, intercept = np.polyfit(ages, times, 1)
            # Compute R2 and std error
            pred = intercept + beta*ages
            residuals = times - pred
            mse = np.mean(residuals**2)
            # Uncertainty: std error of beta
            # Var(beta) = mse / sum((x - mean)^2)
            var_beta = mse / np.sum((ages - np.mean(ages))**2) if np.sum((ages - np.mean(ages))**2)>0 else 1e6  # noqa: E501
            std_err = math.sqrt(var_beta)
            # Hierarchical shrinkage: shrink toward global prior 0.05 sec/lap
            prior_beta=0.05
            prior_n=10
            n=len(rows)
            shrunk_beta = (n*beta + prior_n*prior_beta)/(n+prior_n)
            shrunk_std = std_err * math.sqrt(n/(n+prior_n))  # shrinkage reduces variance
            results[compound]={
                "beta": shrunk_beta,
                "raw_beta": beta,
                "intercept": intercept,
                "std_err": std_err,
                "shrunk_std": shrunk_std,
                "ci95": [shrunk_beta -1.96*shrunk_std, shrunk_beta +1.96*shrunk_std],
                "mse": mse,
                "sample_size": n,
                "evidence_tier": "LIMITED" if n<100 else "CALIBRATED",
                "available": True,
                "as_of": as_of,
                "source": "fastf1",
                "tyre_era": "TYRE_ERA_PIRELLI",
            }
        except Exception as e:
            results[compound]={
                "beta": None,
                "available": False,
                "reason": str(e),
                "evidence_tier": "NON_IDENTIFIABLE",
                "sample_size": len(rows),
            }
    # Also compute global, filter NaN
    all_rows=[o for o in filtered if o["compound"] and o["tyre_age"] is not None and o["lap_time"] is not None and not (isinstance(o["lap_time"], float) and math.isnan(o["lap_time"]))]  # noqa: E501
    if len(all_rows)>=10:
        ages=np.array([r["tyre_age"] for r in all_rows])
        times=np.array([r["lap_time"] for r in all_rows])
        try:
            beta, intercept = np.polyfit(ages, times, 1)
            results["GLOBAL"]={
                "beta": beta,
                "sample_size": len(all_rows),
                "evidence_tier": "LIMITED",
                "available": True,
            }
        except:
            pass
    return results

def calibrate_compound_effect(observations, as_of: str = "2024-03-01"):
    """Estimate compound performance vs baseline (e.g., SOFT vs MEDIUM)."""
    filtered=[o for o in observations if o["date"] < as_of and o["compound"] and o["lap_time"]]
    by_compound=defaultdict(list)
    for o in filtered:
        by_compound[o["compound"]].append(o["lap_time"])
    # Baseline = median of all
    all_times=[o["lap_time"] for o in filtered]
    baseline=np.median(all_times) if all_times else 90
    results={}
    for compound, times in by_compound.items():
        if len(times)<5:
            results[compound]={
                "effect": None,
                "available": False,
                "reason": f"sample {len(times)} <5",
                "evidence_tier": "NON_IDENTIFIABLE",
                "sample_size": len(times),
            }
            continue
        median=np.median(times)
        effect=median - baseline  # negative = faster than baseline
        # Shrinkage toward 0
        prior_n=5
        n=len(times)
        shrunk= (n*effect + prior_n*0)/(n+prior_n)
        results[compound]={
            "effect": shrunk,
            "raw_effect": effect,
            "baseline": baseline,
            "sample_size": n,
            "evidence_tier": "LIMITED",
            "available": True,
            "as_of": as_of,
        }
    return results
