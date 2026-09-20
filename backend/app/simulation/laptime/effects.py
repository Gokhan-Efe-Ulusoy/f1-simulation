"""Effects for decomposition — driver, constructor, progression, tyre, pit, weather, RC."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List

from app.simulation.laptime.models import LapRecord


@dataclass
class DriverEstimate:
    driver_id: str
    n_laps: int
    n_circuits: int
    n_seasons: int
    raw: float
    shrunk: float
    se: float
    tier: str


class DriverEffect:
    """Hierarchical driver pace: global -> era -> driver, optionally circuit-adjusted."""

    def __init__(self, tau: float = 10):
        self.tau = tau
        self.global_mean: float = 0.0
        self.driver_estimates: Dict[str, DriverEstimate] = {}

    def fit(self, records: List[LapRecord], circuit_baseline=None) -> dict:
        # Use residual after circuit baseline if provided
        buckets = defaultdict(list)
        for r in records:
            if r.lap_time_seconds:
                # residual
                base = circuit_baseline.predict(r.circuit, r.season) if circuit_baseline else 94.05
                resid = r.lap_time_seconds - base
                buckets[str(r.driver_number)].append((resid, r))
        # global
        all_resids = [res for lst in buckets.values() for res, _ in lst]
        self.global_mean = statistics.mean(all_resids) if all_resids else 0.0
        for did, lst in buckets.items():
            resids = [x[0] for x in lst]
            n = len(resids)
            raw = statistics.mean(resids) if resids else 0.0
            se = statistics.pstdev(resids) / math.sqrt(n) if n > 1 else 1.0
            shrunk = (n * raw + self.tau * self.global_mean) / (n + self.tau)
            circuits = len(set(x[1].circuit for x in lst))
            seasons = len(set(x[1].season for x in lst))
            tier = "CALIBRATED" if n >= 500 else "LIMITED" if n >= 100 else "PRIOR_ONLY"
            self.driver_estimates[did] = DriverEstimate(did, n, circuits, seasons, raw, shrunk, se, tier)  # noqa: E501
        return {
            "global": self.global_mean,
            "drivers": {k: v.__dict__ for k, v in self.driver_estimates.items()},
            "evidence_tier": "LIMITED",
        }

    def predict(self, driver_id: str) -> float:
        est = self.driver_estimates.get(str(driver_id))
        return est.shrunk if est else 0.0


class ConstructorEffect:
    """Constructor effect — only where sufficient, otherwise LIMITED/NON_IDENTIFIABLE."""

    def __init__(self, tau: float = 10):
        self.tau = tau
        self.constructor_estimates: Dict[str, dict] = {}

    def fit(self, records: List[LapRecord], circuit_baseline=None, driver_effect=None) -> dict:
        # Need constructor field; if sparse, mark non-identifiable
        buckets = defaultdict(list)
        for r in records:
            if r.lap_time_seconds and r.constructor:
                base = circuit_baseline.predict(r.circuit, r.season) if circuit_baseline else 94.05
                d_eff = driver_effect.predict(r.driver_number) if driver_effect else 0.0
                resid = r.lap_time_seconds - base - d_eff
                buckets[r.constructor].append(resid)
        all_resids = [x for lst in buckets.values() for x in lst]
        global_mean = statistics.mean(all_resids) if all_resids else 0.0
        result = {}
        for cons, lst in buckets.items():
            n = len(lst)
            if n < 30:
                result[cons] = {"n": n, "estimate": None, "se": None, "tier": "NON_IDENTIFIABLE", "reason": "insufficient data, driver-constructor confounding"}  # noqa: E501
                continue
            raw = statistics.mean(lst)
            se = statistics.pstdev(lst) / math.sqrt(n) if n > 1 else 1.0
            shrunk = (n * raw + self.tau * global_mean) / (n + self.tau)
            tier = "LIMITED" if n < 300 else "CALIBRATED"
            # Check identifiability: if driver and constructor perfectly correlated (same driver always same constructor), then doubling counting
            result[cons] = {"n": n, "raw": raw, "estimate": shrunk, "se": se, "tier": tier}
        # If overall sparse, mark overall LIMITED
        self.constructor_estimates = result
        status = "LIMITED" if len([v for v in result.values() if v.get("tier") == "CALIBRATED"]) >= 3 else "NON_IDENTIFIABLE"  # noqa: E501
        return {"constructors": result, "status": status, "global": global_mean}


class ProgressionEffect:
    """Race progression associational — NOT fuel."""

    def __init__(self):
        self.coefficients: Dict[str, float] = {}
        self.evidence_tier = "ASSOCIATIONAL"

    def fit(self, records: List[LapRecord]) -> dict:
        # Test specs A-E, but here we fit progression only associational
        # Simple: lap progression beta via OLS lap_time ~ normalized progression
        import numpy as np
        valid = [r for r in records if r.lap_time_seconds and r.lap_number]
        if len(valid) < 100:
            return {"beta": None, "tier": "NON_IDENTIFIABLE"}
        # Compute normalized progression per race: lap_number / max per race
        from collections import defaultdict
        max_per_race = defaultdict(int)
        for r in valid:
            if r.lap_number > max_per_race[r.race_id]:
                max_per_race[r.race_id] = r.lap_number
        xs = []
        ys = []
        for r in valid:
            max_lap = max_per_race[r.race_id] or 60
            prog = r.lap_number / max_lap
            xs.append(prog)
            ys.append(r.lap_time_seconds)
        xs = np.array(xs, dtype=float)
        ys = np.array(ys, dtype=float)
        # OLS
        mx = xs.mean()
        my = ys.mean()
        num = ((xs - mx) * (ys - my)).sum()
        den = ((xs - mx) ** 2).sum()
        beta = num / den if den else 0.0
        # progression coefficient is associational, includes fuel+tyre+traffic
        self.coefficients["race_progress"] = float(beta)
        return {
            "beta_race_progress": float(beta),
            "beta_lap_number": float(beta / 60) if beta else None,  # approx per lap
            "n": len(valid),
            "tier": "RACE_PROGRESSION_ASSOCIATIONAL",
            "warning": "NOT fuel, correlated with tyre age r~0.5",
        }


class TyreEffect:
    """Tyre reassessment with monotonic constraint."""

    def __init__(self):
        self.compound_effects: Dict[str, float] = {}
        self.degradation_beta: float | None = None
        self.constrained_beta: float | None = None
        self.tier: str = "NON_IDENTIFIABLE"

    def fit(self, records: List[LapRecord]) -> dict:
        # Only exact tyre observations 2023-2026
        valid = [r for r in records if r.tyre_age is not None and r.compound in ("soft", "medium", "hard") and r.lap_time_seconds and 50 < r.lap_time_seconds < 400]  # noqa: E501
        if len(valid) < 100:
            return {"status": "NON_IDENTIFIABLE", "n": len(valid)}
        # 1. compound fixed effects: mean lap time per compound vs global
        from collections import defaultdict
        by_comp = defaultdict(list)
        for r in valid:
            by_comp[r.compound].append(r.lap_time_seconds)
        global_mean = statistics.mean([r.lap_time_seconds for r in valid])
        for comp, lst in by_comp.items():
            self.compound_effects[comp] = statistics.mean(lst) - global_mean
        # 2. unconstrained tyre age beta via OLS
        import numpy as np
        xs = np.array([r.tyre_age for r in valid], dtype=float)
        ys = np.array([r.lap_time_seconds for r in valid], dtype=float)
        mx = xs.mean()
        my = ys.mean()
        beta = ((xs - mx) * (ys - my)).sum() / ((xs - mx) ** 2).sum() if ((xs - mx) ** 2).sum() else 0.0  # noqa: E501
        self.degradation_beta = float(beta)
        # 3. monotonic constrained: enforce beta >=0 (increasing age cannot improve lap time)
        # If unconstrained negative, constrained beta = 0 (reject degradation)
        if beta < 0:
            self.constrained_beta = 0.0
            self.tier = "NON_IDENTIFIABLE"
            # Do NOT fit production degradation curve just to get positive number
        else:
            self.constrained_beta = float(beta)
            self.tier = "CANDIDATE"
        # Additional checks: within-stint normalized progression, circuit×compound etc would be done elsewhere
        # For now, report
        return {
            "compound_effects": self.compound_effects,
            "unconstrained_beta": self.degradation_beta,
            "constrained_beta": self.constrained_beta,
            "n": len(valid),
            "tier": self.tier,
            "physically_plausible": self.degradation_beta is not None and self.degradation_beta >= 0,  # noqa: E501
        }


class PitEffect:
    """Pit lap separation — total loss only."""

    def __init__(self):
        self.mean_loss: float = 24.1
        self.median_loss: float = 23.8

    def fit(self, records: List[LapRecord]) -> dict:
        # pit laps are already classified as PIT_LAP via quality filter
        pit_times = [r.lap_time_seconds for r in records if r.lap_time_seconds and (r.is_pit_in or r.is_pit_out)]  # noqa: E501
        valid_times = [r.lap_time_seconds for r in records if r.lap_time_seconds and not (r.is_pit_in or r.is_pit_out) and 50 < r.lap_time_seconds < 400]  # noqa: E501
        if pit_times and valid_times:
            self.mean_loss = statistics.mean(pit_times) - statistics.mean(valid_times)
            self.median_loss = statistics.median(pit_times) - statistics.median(valid_times) if len(pit_times) > 2 else self.mean_loss  # noqa: E501
        return {
            "mean_total_loss": self.mean_loss,
            "median_total_loss": self.median_loss,
            "n_pit_laps": len(pit_times),
            "tier": "LIMITED" if len(pit_times) > 100 else "PRIOR_ONLY",
            "note": "lane_loss and stationary_loss remain NON_IDENTIFIABLE",
        }


class WeatherEffect:
    """Weather — separate observed vs ERA5 vs prior."""

    def fit(self, records: List[LapRecord]) -> dict:
        # records may have is_wet, air_temp, rainfall
        wet = [r for r in records if r.is_wet and r.lap_time_seconds]
        dry = [r for r in records if not r.is_wet and r.lap_time_seconds]
        if len(wet) < 50:
            return {"tier": "PRIOR_ONLY", "n_wet": len(wet), "reason": "insufficient observed wet laps"}  # noqa: E501
        # simple effect: wet slower
        wet_mean = statistics.mean([r.lap_time_seconds for r in wet])
        dry_mean = statistics.mean([r.lap_time_seconds for r in dry]) if dry else wet_mean
        effect = wet_mean - dry_mean
        return {"wet_effect_seconds": effect, "n_wet": len(wet), "n_dry": len(dry), "tier": "LIMITED" if len(wet) < 300 else "CALIBRATED"}  # noqa: E501


class RaceControlEffect:
    """Neutralisation effects — SC/VSC etc, limited historical."""

    def fit(self, records: List[LapRecord]) -> dict:
        flags = defaultdict(list)
        for r in records:
            if r.lap_time_seconds:
                flags[r.race_control_flag or "GREEN"].append(r.lap_time_seconds)
        result = {}
        for flag, lst in flags.items():
            n = len(lst)
            if n < 30:
                result[flag] = {"n": n, "tier": "PRIOR_ONLY", "estimate": None}
            else:
                result[flag] = {"n": n, "mean": statistics.mean(lst), "tier": "LIMITED" if n < 500 else "CALIBRATED"}  # noqa: E501
        # SC/VSC historical is PRIOR_ONLY unless passes gate
        status = "PRIOR_ONLY" if result.get("SAFETY_CAR", {}).get("n", 0) < 100 else "LIMITED"
        return {"flags": result, "status": status}
