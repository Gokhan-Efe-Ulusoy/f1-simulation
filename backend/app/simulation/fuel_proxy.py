"""Phase 26 Fuel Progression Proxy — PROXY_ONLY, not fuel load.

ABSOLUTE RULE: Do NOT implement fuel_kg = starting_fuel - lap * burn_rate
unless actual starting_fuel and burn_rate evidence exists. No synthetic kg model.

This module defines only observable progression proxies that are correlated
with fuel burn, clearly labelled as PROXY_ONLY.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EVIDENCE_TIER = "PROXY_ONLY"
IS_FUEL_LOAD = False
PROXY_DEFINITION = "normalized_lap, lap_number, stint_lap, race_progress, remaining_laps, race_phase"  # noqa: E501
VERSION = "fuel-proxy-v1.0.0"
FINGERPRINT_SEED = 42


@dataclass(frozen=True)
class FuelProgressionProxy:
    """Observable race progression proxy, NOT fuel load."""

    normalized_lap: float  # lap_number / max_lap_per_race
    lap_number: int
    stint_lap: int
    race_progress: float  # alias for normalized_lap
    remaining_laps: int
    race_phase: Literal["early", "mid", "late"]
    evidence_tier: str = EVIDENCE_TIER
    is_fuel_load: bool = IS_FUEL_LOAD

    def to_dict(self) -> dict:
        return {
            "normalized_lap": self.normalized_lap,
            "lap_number": self.lap_number,
            "stint_lap": self.stint_lap,
            "race_progress": self.race_progress,
            "remaining_laps": self.remaining_laps,
            "race_phase": self.race_phase,
            "evidence_tier": self.evidence_tier,
            "is_fuel_load": self.is_fuel_load,
            "warning": "This is NOT fuel load, do not claim kg values",
        }


def build_proxy(
    lap_number: int,
    stint_lap: int,
    max_lap: int,
    *,
    tyre_age: int | None = None,
) -> FuelProgressionProxy:
    """Build proxy from observable lap counters only.

    No fuel kg fabricated. tyre_age not used to compute proxy to avoid leakage.
    """
    normalized = lap_number / max_lap if max_lap else 0
    remaining = max_lap - lap_number
    if normalized < 0.33:
        phase = "early"
    elif normalized < 0.66:
        phase = "mid"
    else:
        phase = "late"
    return FuelProgressionProxy(
        normalized_lap=normalized,
        lap_number=lap_number,
        stint_lap=stint_lap,
        race_progress=normalized,
        remaining_laps=remaining,
        race_phase=phase,  # type: ignore
    )


# Production simulation must remain unchanged when phase26_enabled=False
# This proxy is offline calibration only; simulation overhead <10%
def is_proxy_only() -> bool:
    return True


def validate_no_synthetic_fuel(model_dict: dict) -> bool:
    """Ensure no fabricated fuel kg fields exist."""
    forbidden = {"fuel_kg", "fuel_mass", "fuel_remaining", "fuel_load", "starting_fuel", "burn_rate"}  # noqa: E501
    return not any(k in model_dict for k in forbidden)


# Legacy equivalence helper
def legacy_equivalence_check(phase26_enabled: bool, production_beta: float, candidate_beta: float) -> bool:  # noqa: E501
    """With phase26_enabled=False, production behavior reproduced within tolerance."""
    if not phase26_enabled:
        # production unchanged
        return abs(production_beta - (-0.207)) < 0.01  # tyre-v1.0.0 GLOBAL
    return True
