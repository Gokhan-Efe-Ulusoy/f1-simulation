"""Phase 21 — Intervention registry: allowlists, bounds, tiers, pathways, eras.

Single source of truth for what the scenario layer may touch. Anything not
listed here is rejected (no silent pass-through, no arbitrary execution).
Bounds reuse domain models wherever they exist (setup validator, WeatherState
ranges, RC policy ranges); only enumerated here, never re-derived.
"""
from __future__ import annotations

from typing import Any

# --- Setup parameter names: enumerated from the Phase 20 model (no duplication
# of bounds; bounds are enforced via SetupValidator at compile time). ---
try:
    from app.simulation.setup.models import SetupParameters as _SetupParameters

    SETUP_PARAMS: tuple[str, ...] = tuple(sorted(_SetupParameters.model_fields.keys()))
except Exception:  # pragma: no cover - import guard for docs-only contexts
    SETUP_PARAMS = (
        "front_wing", "rear_wing", "ride_height_front", "ride_height_rear",
        "front_anti_roll", "rear_anti_roll", "front_spring", "rear_spring",
        "brake_bias", "diff_entry", "diff_mid", "diff_exit",
        "front_camber", "rear_camber", "front_toe", "rear_toe",
        "tyre_pressure_front", "tyre_pressure_rear",
    )

# --- Weather: allowlisted initial-state fields with WeatherState ranges. ---
WEATHER_FIELDS: dict[str, tuple[float, float]] = {
    "rainfall_mm_h": (0.0, 100.0),
    "track_wetness": (0.0, 1.0),
    "air_temperature_c": (-10.0, 50.0),
    "track_temperature_c": (-5.0, 65.0),
    "humidity_pct": (0.0, 100.0),
    "pressure_hpa": (900.0, 1100.0),
    "wind_speed_mps": (0.0, 50.0),
    "wind_direction_deg": (0.0, 360.0),
    "visibility_km": (0.0, 20.0),
    "cloud_cover_pct": (0.0, 100.0),
}

# --- Race control: flags actually consumed by the vectorized path + the two
# policy thresholds it honours (vectorized_montecarlo.py). Anything else
# (forced SC at lap X, red-flag timing, restart scripting) is UNSUPPORTED. ---
RC_FLAGS: tuple[str, ...] = (
    "enabled",
    "enable_yellow",
    "enable_vsc",
    "enable_safety_car",
    "enable_red_flag",
    "enable_first_lap_incidents",
    "weather_coupling",
)
RC_THRESHOLDS: dict[str, tuple[float, float]] = {
    "wetness_red_flag_threshold": (0.0, 1.0),
    "rainfall_red_flag_threshold_mm_h": (0.0, 100.0),
}

# --- Tyre compounds: canonical map keys minus UNKNOWN (kernels.py). ---
try:
    from app.simulation.tyre.kernels import COMPOUND_MAP as _COMPOUND_MAP

    TYRE_COMPOUNDS: tuple[str, ...] = tuple(
        sorted(k for k in _COMPOUND_MAP.keys() if k != "UNKNOWN")
    )
except Exception:  # pragma: no cover
    TYRE_COMPOUNDS = ("SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET")

# --- Pace-delta bounds (model interventions, pace units of base_pace). ---
PACE_DELTA_MIN = -3.0
PACE_DELTA_MAX = 3.0

# --- Pit-loss channel (Phase 22). The vectorized path historically applied no
# pit-lane time loss (extra stops showed tyre-freshness benefit only). An
# explicit `strategy.pit_loss_seconds` intervention adds a deterministic,
# per-pit-stop time cost (seconds) on each scheduled pit lap. Default 0.0
# (disabled) reproduces legacy behavior exactly. The reference value below is
# the *mean* of the repository's own PitStopModel prior
# (pit_lane_drive_through_time 22.0s + stationary_base 2.4s); it is PRIOR_ONLY,
# never calibrated, and never applied unless explicitly requested. ---
PIT_LOSS_RANGE: tuple[float, float] = (0.0, 60.0)
PIT_LOSS_DEFAULT_SECONDS: float = 0.0
PIT_LOSS_PRIOR_REFERENCE_SECONDS: float = 24.4  # 22.0 + 2.4 (PitStopModel means)
PIT_LOSS_EVIDENCE_TIER: str = "PRIOR_ONLY"

# --- Ops allowed per family (enforced by validation). ---
FAMILY_OPS: dict[str, tuple[str, ...]] = {
    "setup": ("SET_VALUE", "ADD_DELTA"),
    "strategy": ("SET_VALUE",),
    "tyre": ("SET_VALUE",),
    "race_control": ("SET_VALUE", "ENABLE", "DISABLE"),
    "weather": ("SET_VALUE", "ADD_DELTA", "MULTIPLY", "ENABLE", "DISABLE"),
    "driver": ("ADD_DELTA",),
    "car": ("ADD_DELTA",),
}

# --- Parameters allowed per family. ---
FAMILY_PARAMS: dict[str, tuple[str, ...]] = {
    "setup": SETUP_PARAMS,
    "strategy": ("pit_laps", "pit_loss_seconds"),
    "tyre": ("starting_compound", "pit_compound", "stints"),
    "race_control": RC_FLAGS + tuple(RC_THRESHOLDS.keys()),
    "weather": tuple(WEATHER_FIELDS.keys()) + ("enabled",),
    "driver": ("pace_delta",),
    "car": ("pace_delta",),
}

# --- Effect evidence tier per family (Monte Carlo never upgrades these). ---
FAMILY_TIERS: dict[str, str] = {
    "setup": "PRIOR_ONLY",
    "strategy": "PRIOR_ONLY",
    "tyre": "PRIOR_ONLY",
    "race_control": "PRIOR_ONLY",
    "weather": "PRIOR_ONLY",
    "driver": "PRIOR_ONLY",
    "car": "PRIOR_ONLY",
}

# --- Declared causal pathways (explanation may only cite families present
# in the applied trace; each pathway mirrors an implemented code path). ---
PATHWAYS: dict[str, list[str]] = {
    "setup": [
        "setup parameters",
        "vehicle effects (downforce / drag / balance)",
        "per-lap pace offsets",
        "race dynamics",
        "finish distribution",
    ],
    "strategy": [
        "pit-lap schedule",
        "tyre age resets at pit laps",
        "pit-lane time loss (only when pit_loss_seconds explicitly enabled; 0 by default)",
        "degradation profile over the race",
        "per-lap pace",
        "race dynamics",
        "finish distribution",
    ],
    "tyre": [
        "stint compound sequence",
        "compound degradation rates",
        "per-lap pace",
        "race dynamics",
        "finish distribution",
    ],
    "race_control": [
        "neutralisation trajectories (shared across drivers)",
        "pace control / field compression / overtake suppression",
        "race dynamics",
        "finish distribution",
    ],
    "weather": [
        "initial weather state override",
        "weather trajectories (shared across drivers)",
        "grip / per-lap pace (+ tyre environment, + race-control coupling)",
        "race dynamics",
        "finish distribution",
    ],
    "driver": [
        "driver pace mean",
        "base-pace sampling (common random numbers)",
        "per-lap pace",
        "finish distribution",
    ],
    "car": [
        "constructor pace mean (correlated across teammates)",
        "base-pace sampling (common random numbers)",
        "per-lap pace",
        "finish distribution",
    ],
}

# --- Leakage blocklist: parameter substrings that would smuggle realized
# future information into a historical run. Matched case-insensitively. ---
LEAKAGE_SUBSTRINGS: tuple[str, ...] = (
    "actual_",
    "observed_result",
    "future_",
    "realized",
    "realised",
    "winner",
    "podium_result",
    "finishing_position",
    "final_position",
    "championship",
    "standing",
    "points_table",
    "result_table",
    "observed_pit",
    "observed_weather",
)

# Structural Scenario fields no family may target (defense in depth).
STRUCTURAL_FIELDS: tuple[str, ...] = (
    "scenario_id", "as_of", "date", "drivers", "grid_order", "season_id",
    "circuit_id", "type", "calibration", "dataset", "temporal_context",
)

# --- Era support. Boundaries mirror HistoricalStateBuilder._era_for_season
# (scenario_v14.py). Setup params are model dials, not historical claims:
# SUPPORTED in the model era, UNKNOWN (allowed + flagged) before it. ---
MODEL_ERA = "2022-2026"


def era_for_season(season_id: Any) -> str:
    """Era bucket for a season id (same boundaries as scenario_v14)."""
    try:
        y = int(str(season_id)[:4])
    except Exception:
        return MODEL_ERA
    for name, s, e in [
        ("1950-1960", 1950, 1960), ("1961-1970", 1961, 1970),
        ("1971-1982", 1971, 1982), ("1983-1987", 1983, 1987),
        ("1988-1993", 1988, 1993), ("1994-1997", 1994, 1997),
        ("1998-2008", 1998, 2008), ("2009-2013", 2009, 2013),
        ("2014-2021", 2014, 2021), ("2022-2026", 2022, 2026),
    ]:
        if s <= y <= e:
            return name
    return MODEL_ERA


def era_support(family: str, season_id: Any) -> tuple[str, str]:
    """Return (status, note) where status in SUPPORTED|UNKNOWN.

    Nothing is UNSUPPORTED by era: pre-2022 setup dials are legitimate MODEL
    interventions, flagged UNKNOWN applicability (NON_IDENTIFIABLE tier note).
    """
    era = era_for_season(season_id)
    if family == "setup" and era != MODEL_ERA:
        return (
            "UNKNOWN",
            f"setup dials are model parameters; applicability to era {era} is "
            f"unknown (no historical setup data). Allowed as model intervention.",
        )
    return ("SUPPORTED", f"{family} mechanism is era-agnostic in this model (era {era}).")


def is_leakage_param(parameter: str) -> bool:
    p = str(parameter).lower()
    if p in ("result", "results", "winner", "podium"):
        return True
    if p in STRUCTURAL_FIELDS:
        return True
    return any(s in p for s in LEAKAGE_SUBSTRINGS)
