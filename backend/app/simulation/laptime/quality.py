"""Deterministic lap-quality filter — Phase 27.

Every exclusion has a reason. Do NOT silently delete.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List, Tuple
from app.simulation.laptime.models import LapRecord, LapQuality


# Thresholds
MIN_LAP_TIME = 50.0
MAX_LAP_TIME = 400.0
MAX_TYRE_AGE = 60
FORMATION_LAP_MAX = 1  # lap 1 is formation/race start, not counted as valid racing lap for decomposition  # noqa: E501


def classify_lap(record: LapRecord) -> LapQuality:
    """Deterministic quality classification."""
    # Missing
    if record.lap_time_seconds is None:
        return LapQuality.MISSING
    lt = record.lap_time_seconds
    # Invalid time range
    if lt < MIN_LAP_TIME or lt > MAX_LAP_TIME:
        return LapQuality.INVALID
    # Pit lap: explicit flag or stint boundary
    if record.is_pit_in or record.is_pit_out or record.stint_lap == 1 and record.lap_number != 1:
        # stint_lap==1 except race start indicates pit out
        # is_pit_in/out are authoritative if present
        return LapQuality.PIT_LAP
    # Formation: lap 1 is race start, not steady-state pacing
    if record.lap_number == 1:
        return LapQuality.FORMATION
    # Safety car / neutralised
    if record.race_control_flag in ("SAFETY_CAR", "VSC", "DOUBLE_YELLOW", "YELLOW"):
        return LapQuality.SAFETY_CAR
    # Red flag
    if record.race_control_flag in ("RED_FLAG", "RED"):
        return LapQuality.RED_FLAG
    # Outlier: tyre age beyond plausible or extreme compound mismatch (e.g., wet on dry)
    if record.tyre_age is not None and (record.tyre_age < 0 or record.tyre_age > MAX_TYRE_AGE):
        return LapQuality.OUTLIER
    # Otherwise valid
    return LapQuality.VALID


class LapQualityFilter:
    """Deterministic filter with audit."""

    def __init__(self):
        self.counts = Counter()
        self.by_season: Dict[int, Counter] = defaultdict(Counter)
        self.by_circuit: Dict[str, Counter] = defaultdict(Counter)
        self.by_race: Dict[str, Counter] = defaultdict(Counter)
        self.by_driver: Dict[int, Counter] = defaultdict(Counter)
        self.by_reason: Counter = Counter()

    def filter(self, records: List[LapRecord]) -> Tuple[List[LapRecord], List[Tuple[LapRecord, LapQuality]]]:  # noqa: E501
        valid = []
        excluded = []
        for rec in records:
            q = classify_lap(rec)
            self.counts[q.value] += 1
            self.by_season[rec.season][q.value] += 1
            self.by_circuit[rec.circuit][q.value] += 1
            self.by_race[rec.race_id][q.value] += 1
            self.by_driver[rec.driver_number][q.value] += 1
            self.by_reason[q.value] += 1
            if q == LapQuality.VALID:
                valid.append(rec)
            else:
                excluded.append((rec, q))
        return valid, excluded

    def audit(self) -> dict:
        return {
            "total": sum(self.counts.values()),
            "counts": dict(self.counts),
            "by_season": {str(k): dict(v) for k, v in self.by_season.items()},
            "by_circuit": {k: dict(v) for k, v in self.by_circuit.items()},
            "by_race": {k: dict(v) for k, v in self.by_race.items()},
            "by_driver": {str(k): dict(v) for k, v in self.by_driver.items()},
            "by_reason": dict(self.by_reason),
        }
