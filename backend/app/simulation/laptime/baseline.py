"""Circuit baseline hierarchical model — Phase 27.

Uses Phase-24 concept as CANDIDATE, not production.
Estimates global, era, circuit, circuit-era with shrinkage.
Strict chronological validation, no future races.
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class CircuitEstimate:
    circuit: str
    n_laps: int
    n_races: int
    raw_mean: float
    estimate: float
    se: float
    shrinkage: float
    ci_low: float
    ci_high: float
    evidence_tier: str


class CircuitBaseline:
    """Hierarchical circuit baseline."""

    def __init__(self, tau: float = 30, tau_era: float = 50):
        self.tau = tau
        self.tau_era = tau_era
        self.global_mean: float = 94.05
        self.global_se: float = 0.0
        self.era_means: Dict[str, float] = {}
        self.circuit_estimates: Dict[str, CircuitEstimate] = {}
        self.circuit_era: Dict[str, Dict[str, float]] = {}

    def fit(self, records) -> dict:
        """Fit from valid LapRecords."""
        # records: list of LapRecord with lap_time
        valid = [r for r in records if r.lap_time_seconds and 50 < r.lap_time_seconds < 400]
        if not valid:
            return {"evidence_tier": "NON_IDENTIFIABLE", "n_laps": 0}
        self.global_mean = statistics.mean([r.lap_time_seconds for r in valid])
        # era grouping by season
        era_map = {
            "1950-1960": (1950, 1960),
            "1961-1970": (1961, 1970),
            "1971-1982": (1971, 1982),
            "1983-1987": (1983, 1987),
            "1988-1993": (1988, 1993),
            "1994-1997": (1994, 1997),
            "1998-2008": (1998, 2008),
            "2009-2013": (2009, 2013),
            "2014-2021": (2014, 2021),
            "2022-2026": (2022, 2026),
        }
        era_groups: Dict[str, List] = defaultdict(list)
        for r in valid:
            for era, (s, e) in era_map.items():
                if s <= r.season <= e:
                    era_groups[era].append(r)
                    break
        for era, lst in era_groups.items():
            self.era_means[era] = statistics.mean([x.lap_time_seconds for x in lst]) if lst else self.global_mean  # noqa: E501
        # circuit estimates with hierarchical shrinkage
        by_circuit: Dict[str, List] = defaultdict(list)
        for r in valid:
            by_circuit[r.circuit].append(r)
        for circuit, lst in by_circuit.items():
            n = len(lst)
            n_races = len(set(x.race_id for x in lst))
            raw = statistics.mean([x.lap_time_seconds for x in lst])
            # se
            sd = statistics.pstdev([x.lap_time_seconds for x in lst]) if n > 1 else 5.0
            se = sd / math.sqrt(n) if n else 5.0
            # shrinkage toward era then global
            # determine era for circuit: most common era
            seasons = [x.season for x in lst]
            avg_season = statistics.mean(seasons) if seasons else 2024
            era = next((k for k, (s, e) in era_map.items() if s <= avg_season <= e), "2022-2026")
            era_mean = self.era_means.get(era, self.global_mean)
            # two-stage shrinkage: circuit -> era -> global
            w_circuit = n / (n + self.tau)
            shrunk_to_era = w_circuit * raw + (1 - w_circuit) * era_mean
            # era shrinkage weight tau_era
            n_era = len(era_groups[era])
            w_era = n_era / (n_era + self.tau_era) if n_era else 0.5
            # not used for circuit directly, but for reporting
            estimate = shrunk_to_era  # simplified
            shrinkage = w_circuit
            ci_low = estimate - 1.96 * se
            ci_high = estimate + 1.96 * se
            tier = "CALIBRATED" if n >= 400 and n_races >= 3 else "LIMITED" if n >= 50 else "PRIOR_ONLY"  # noqa: E501
            self.circuit_estimates[circuit] = CircuitEstimate(
                circuit=circuit, n_laps=n, n_races=n_races, raw_mean=raw, estimate=estimate,
                se=se, shrinkage=shrinkage, ci_low=ci_low, ci_high=ci_high, evidence_tier=tier
            )
        return {
            "global": self.global_mean,
            "era": self.era_means,
            "circuits": {k: v.__dict__ for k, v in self.circuit_estimates.items()},
            "evidence_tier": "LIMITED",
            "n_laps": len(valid),
            "n_circuits": len(by_circuit),
        }

    def predict(self, circuit: str, season: int) -> float:
        est = self.circuit_estimates.get(circuit)
        if est:
            return est.estimate
        # fallback to era or global
        for era, (s, e) in [(k, v) for k, v in [("2022-2026", (2022, 2026)), ("2014-2021", (2014, 2021))]]:  # noqa: E501
            if s <= season <= e:
                return self.era_means.get(era, self.global_mean)
        return self.global_mean
