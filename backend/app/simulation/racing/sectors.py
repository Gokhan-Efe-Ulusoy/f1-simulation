"""Per-sector simulation primitives (Phase 8).

Lap time stays authoritative: sector times are an exact partition of the
lap time (S1+S2+S3 == lap within float tolerance). Sector characteristics
shape the *distribution* of pace across sectors and feed sector-level
dirty-air / overtake / defense decisions. No effect is double-applied at
both lap and sector level: the lap total is never re-summed from modified
sectors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SectorState:
    """Per-sector snapshot for one driver on one lap."""

    sector_index: int
    sector_type: str = "medium"  # dominant corner type label
    sector_distance_km: float = 0.0
    track_wetness: float = 0.0
    racing_line_wetness: float = 0.0
    following_distance: float = 0.0
    dirty_air_loss: float = 0.0  # sec, diagnostic share for this sector
    fuel_used: float = 0.0  # kg share for this sector
    ers_used: float = 0.0  # energy share for this sector
    tyre_wear_delta: float = 0.0
    drs_available: bool = False
    battle_state: str | None = None
    sector_time: float = 0.0
    cumulative_time: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


def compute_sector_weights(track: Any, car: Any = None, driver: Any = None) -> list[float]:
    """Compute normalized sector weights summing exactly to 1.0.

    Weights start from sector lengths, then tilt toward sectors matching
    car strengths (aero/power/traction/braking) and driver skill.
    All adjustments are small and symmetric around 1.0 so no sector
    dominates pathologically.
    """
    n = int(getattr(track, "number_of_sectors", 3) or 3)
    lengths = list(getattr(track, "sector_lengths_km", []) or [])
    if len(lengths) != n or sum(lengths) <= 0:
        weights = [1.0 / n] * n
    else:
        total = sum(lengths)
        weights = [length / total for length in lengths]

    aero = float(getattr(car, "aero_efficiency", 50)) if car is not None else 50.0
    traction = float(getattr(car, "traction", 75)) if car is not None else 75.0
    braking = float(getattr(car, "braking_stability", 75)) if car is not None else 75.0
    power_proxy = float(getattr(car, "drs_effectiveness", 75)) if car is not None else 75.0

    adjusted: list[float] = []
    for s in range(n):
        try:
            aero_dep = float(track.get_sector_aero_dependency(s))
            traction_dem = float(track.get_sector_traction_demand(s))
            braking_dif = float(track.get_sector_braking_difficulty(s))
            straight = float(track.get_sector_straight_length(s))
        except Exception:
            aero_dep, traction_dem, braking_dif, straight = 50.0, 50.0, 50.0, 0.5
        tilt = 1.0
        tilt += (aero_dep - 50.0) / 100.0 * (aero - 50.0) / 100.0 * 0.2
        tilt += (traction_dem - 50.0) / 100.0 * (traction - 75.0) / 100.0 * 0.15
        tilt += (braking_dif - 50.0) / 100.0 * (braking - 75.0) / 100.0 * 0.1
        tilt += (straight - 0.5) * (power_proxy - 75.0) / 100.0 * 0.1
        adjusted.append(max(0.5, weights[s] * tilt))

    total = sum(adjusted)
    if total <= 0:
        return [1.0 / n] * n
    return [w / total for w in adjusted]


def split_lap_into_sectors(lap_time: float, weights: list[float]) -> list[float]:
    """Split a lap time into sectors that sum back exactly (last = remainder)."""
    n = len(weights)
    if n == 0:
        return []
    sectors = [lap_time * w for w in weights[:-1]]
    sectors.append(lap_time - sum(sectors))
    return [max(0.0, s) for s in sectors]


def sector_gap_trace(
    leader_sectors: list[float],
    follower_sectors: list[float],
    start_gap: float,
) -> list[float]:
    """Cumulative gap after each sector given a starting gap (seconds)."""
    gaps: list[float] = []
    running = start_gap
    for lead, follow in zip(leader_sectors, follower_sectors, strict=False):
        running += follow - lead
        gaps.append(running)
    return gaps
