"""Phase 20 — Setup pace offsets for Monte Carlo integration.

Shared helper used by vectorized (N>=50) path so that setup has a REAL,
deterministic effect on lap times (not stored-and-ignored).

Design:
- Offsets are seconds-per-lap, deterministic (no RNG).
- Baseline setup (or setup disabled) -> offset 0.0 exactly -> legacy preserved.
- Global `parameters` apply to all drivers; per-driver `drivers.{id}`
  overrides allow counterfactuals (one driver changes setup).
- Car/Track are constructed from defaults + calendar lookup; all
  coefficients PRIOR_ONLY (see engine.py).
"""
from __future__ import annotations

from typing import Any

from app.simulation.setup.models import (
    SetupState,
    SetupMode,
    EvidenceTier,
    create_baseline_setup,
    create_setup_from_dict,
)
from app.simulation.setup.engine import SetupEngine
from app.simulation.setup.validator import SetupValidator

_validator = SetupValidator()
_engine = SetupEngine(evidence_tier=EvidenceTier.PRIOR_ONLY)


def _parse_setup_mods(scenario: Any) -> dict[str, Any]:
    try:
        mods = getattr(scenario, "hypothetical_modifiers", {}) or {}
        sm = mods.get("setup", {}) if isinstance(mods.get("setup"), dict) else {}
        if not isinstance(sm, dict):
            return {}
        return sm
    except Exception:
        return {}


def is_setup_enabled(scenario: Any, engine_flag: bool = True) -> bool:
    """Resolve setup enabled flag (engine default + scenario override)."""
    sm = _parse_setup_mods(scenario)
    try:
        mods = getattr(scenario, "hypothetical_modifiers", {}) or {}
        if sm.get("enabled") is False or mods.get("setup_enabled") is False:
            return False
        if sm.get("enabled") is True or mods.get("setup_enabled") is True:
            return True
    except Exception:
        pass
    return bool(engine_flag)


def _lookup_track(circuit_id: str):  # -> Track
    from app.simulation.models.track import Track, get_2024_calendar

    try:
        for t in get_2024_calendar():
            if t.id == circuit_id:
                return t
    except Exception:
        pass
    return Track(id=circuit_id or "unknown", name=circuit_id or "unknown", country="", city="")


def _default_car(car_id: str, constructor_id: str = ""):
    from app.simulation.models.car import Car

    return Car(id=car_id or "default", name=car_id or "default",
               team_id=constructor_id or "default", engine_id="default", year=2024)


def setup_states_for_scenario(scenario: Any) -> dict[str, SetupState]:
    """Build SetupState per driver from scenario modifiers.

    Returns {} when setup disabled (caller treats as zero offset).
    """
    if not is_setup_enabled(scenario, True):
        return {}
    sm = _parse_setup_mods(scenario)
    global_params = sm.get("parameters", {}) if isinstance(sm.get("parameters"), dict) else {}
    per_driver = sm.get("drivers", {}) if isinstance(sm.get("drivers"), dict) else {}
    mode_raw = sm.get("mode", "counterfactual" if (global_params or per_driver) else "hypothetical")
    try:
        mode = SetupMode(str(mode_raw))
    except Exception:
        mode = SetupMode.HYPOTHETICAL

    drivers = list(getattr(scenario, "drivers", []) or [])
    if not drivers:
        for did in list(getattr(scenario, "grid_order", []) or []):
            drivers.append({"driver_id": did, "constructor_id": "", "car_id": did})

    states: dict[str, SetupState] = {}
    for d in drivers:
        if isinstance(d, dict):
            did = d.get("driver_id", "unknown")
            cid = d.get("constructor_id", "")
            car_id = d.get("car_id", did)
        else:
            did = getattr(d, "driver_id", "unknown")
            cid = getattr(d, "constructor_id", "")
            car_id = getattr(d, "car_id", did)
        params: dict[str, float] = {}
        if isinstance(global_params, dict):
            params.update(global_params)
        drv_override = per_driver.get(did, {}) if isinstance(per_driver, dict) else {}
        if isinstance(drv_override, dict):
            # Allow {"parameters": {...}} or flat {...}
            if isinstance(drv_override.get("parameters"), dict):
                params.update(drv_override["parameters"])
            else:
                params.update({k: v for k, v in drv_override.items() if isinstance(v, (int, float))})  # noqa: E501
        if params:
            st = create_setup_from_dict(params, car_id=car_id, constructor_id=cid,
                                        season=getattr(scenario, "season_id", "2024"),
                                        track_id=getattr(scenario, "circuit_id", None),
                                        mode=mode)
        else:
            st = create_baseline_setup(car_id=car_id, constructor_id=cid,
                                       season=getattr(scenario, "season_id", "2024"),
                                       track_id=getattr(scenario, "circuit_id", "unknown"),
                                       mode=mode)
        # Validate + clamp (never crash simulation on bad user input)
        try:
            res = _validator.validate(st)
            if not res.is_valid:
                st, _ = _validator.validate_and_clamp(st)
        except Exception:
            pass
        states[did] = st
    return states


def setup_offsets_for_scenario(scenario: Any, base_lap_time: float = 90.0) -> dict[str, float]:
    """Per-driver seconds-per-lap setup offset. 0.0 == baseline/legacy.

    Uses SetupEngine.compute_lap_time_delta total. Deterministic, no RNG.
    """
    states = setup_states_for_scenario(scenario)
    if not states:
        return {}
    track = _lookup_track(getattr(scenario, "circuit_id", "unknown"))
    offsets: dict[str, float] = {}
    for did, st in states.items():
        try:
            car = _default_car(st.car_id, st.constructor_id)
            effects = _engine.compute_effects(st, car, track)
            contrib = _engine.compute_lap_time_delta(effects, base_lap_time, track)
            offsets[did] = float(contrib.get("total", 0.0))
        except Exception:
            offsets[did] = 0.0
    # If every offset is ~0 (all baseline), return {} to signal legacy path
    try:
        if all(abs(v) < 1e-12 for v in offsets.values()):
            return {}
    except Exception:
        pass
    return offsets


def setup_fingerprints_for_scenario(scenario: Any) -> dict[str, str]:
    """Per-driver setup fingerprints (deterministic)."""
    states = setup_states_for_scenario(scenario)
    return {did: (st.fingerprint or "") for did, st in states.items()}
