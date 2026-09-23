"""Phase 21 — Scenario compiler: baseline + interventions -> counterfactual.

Immutable: the baseline Scenario is deep-copied; the caller's object is never
mutated. Interventions apply in list order to hypothetical_modifiers
namespaces that the existing engines already consume (setup / weather /
race_control / tyre+strategy pit schedule / performance pace deltas).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.simulation.scenario.models import Intervention, InterventionTrace, ScenarioSpec
from app.simulation.scenario.registry import PATHWAYS
from app.simulation.scenario.validation import (
    ScenarioValidationError,
    check_spec,
    scenario_constructors,
    scenario_drivers,
    total_laps_for,
)


def _fam(iv: Intervention) -> str:
    return iv.family.value if hasattr(iv.family, "value") else str(iv.family)


def _op(iv: Intervention) -> str:
    return iv.op.value if hasattr(iv.op, "value") else str(iv.op)


def _versions() -> dict[str, str]:
    try:
        from app.simulation import version as V

        return {
            "dataset": getattr(V, "DATASET_VERSION", "f1-dataset-v1.3"),
            "calibration": getattr(V, "CALIBRATION_VERSION", "calibration-v1.0.0"),
            "model": getattr(V, "MODEL_VERSION", "0.9.0"),
            "engine": getattr(V, "RACEENGINE_VERSION", "raceengine-v2.2.0"),
            "scenario": getattr(V, "SCENARIO_MODEL_VERSION", "scenario-v1.0.0"),
            "strategy": getattr(V, "STRATEGY_MODEL_VERSION", "strategy-v1.1.0"),
            "weather": getattr(V, "WEATHER_MODEL_VERSION", "weather-v1.0.0"),
            "race_control": getattr(V, "RACE_CONTROL_MODEL_VERSION", "racecontrol-v1.0.0"),
            "setup": getattr(V, "SETUP_MODEL_VERSION", "setup-v1.0.0"),
        }
    except Exception:
        return {"model": "unknown"}


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _fp16(payload: Any) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()[:16]


def scenario_content_hash(scenario: Any) -> str:
    """Content hash of a Scenario (input-level, no versions/seed)."""
    try:
        payload = {
            "scenario_id": getattr(scenario, "scenario_id", ""),
            "type": getattr(scenario, "type", ""),
            "season_id": getattr(scenario, "season_id", ""),
            "circuit_id": getattr(scenario, "circuit_id", ""),
            "date": getattr(scenario, "date", ""),
            "as_of": getattr(scenario, "as_of", ""),
            "drivers": getattr(scenario, "drivers", []),
            "grid_order": getattr(scenario, "grid_order", []),
            "race_distance": getattr(scenario, "race_distance", {}),
            "historical_mode": getattr(scenario, "historical_mode", True),
            "hypothetical_modifiers": getattr(scenario, "hypothetical_modifiers", {}) or {},
        }
    except Exception:
        payload = {"scenario": str(scenario)}
    return _fp16(payload)


def baseline_fingerprint(scenario: Any) -> str:
    return _fp16({"baseline": scenario_content_hash(scenario), "versions": _versions()})


def spec_fingerprint(spec: ScenarioSpec, baseline_content_hash: str) -> str:
    payload = {
        "baseline": baseline_content_hash,
        "spec_id": spec.spec_id,
        "scenario_type": spec.scenario_type,
        "interventions": [
            {
                "family": _fam(iv),
                "op": _op(iv),
                "target": str(iv.target),
                "parameter": str(iv.parameter),
                "value": iv.value,
            }
            for iv in spec.interventions
        ],
        "versions": _versions(),
        "seed": spec.seed,
        "simulations": spec.simulations,
    }
    return _fp16(payload)


# ---------------------------------------------------------------------------
# Baseline value resolution (for traces; deterministic, no RNG)
# ---------------------------------------------------------------------------

def _baseline_setup_value(baseline: Any, driver_id: str, param: str) -> Any:
    try:
        from app.simulation.setup.offsets import setup_states_for_scenario

        states = setup_states_for_scenario(baseline)
        st = states.get(driver_id)
        if st is not None:
            return float(getattr(st.parameters, param).value)
    except Exception:
        pass
    return None


def _baseline_weather_value(baseline: Any, field: str) -> Any:
    try:
        from app.simulation.weather.engine import WeatherEngine

        eng = WeatherEngine(as_of=getattr(baseline, "as_of", "2024-03-01"))
        ws = eng.initial_state_for_scenario(baseline)
        return getattr(ws, field, None)
    except Exception:
        return None


def _baseline_rc_value(baseline: Any, param: str) -> Any:
    if param == "enabled":
        try:
            mods = getattr(baseline, "hypothetical_modifiers", {}) or {}
            rc = mods.get("race_control", {})
            if isinstance(rc, dict) and rc.get("enabled") is False:
                return False
        except Exception:
            pass
        return True
    if param in (
        "enable_yellow", "enable_vsc", "enable_safety_car", "enable_red_flag",
        "enable_first_lap_incidents", "weather_coupling",
    ):
        try:
            mods = getattr(baseline, "hypothetical_modifiers", {}) or {}
            rc = mods.get("race_control", {}) if isinstance(mods.get("race_control"), dict) else {}
            key = {"enable_yellow": "enable_yellow_flags"}.get(param, param)
            v = rc.get(param, rc.get(key, None))
            return True if v is None else bool(v)
        except Exception:
            return True
    try:
        from app.simulation.race_control.policy import DEFAULT_RACE_CONTROL_POLICY

        return getattr(DEFAULT_RACE_CONTROL_POLICY, param, None)
    except Exception:
        return None


def _default_pit_laps(total: int) -> list[int]:
    return [lap for lap in range(1, total + 1) if lap % 20 == 0 and lap != total]


# ---------------------------------------------------------------------------
# Modifier writers (one per family; mirror engine-consumed formats)
# ---------------------------------------------------------------------------

def _ensure_mods(scenario: Any) -> dict[str, Any]:
    mods = getattr(scenario, "hypothetical_modifiers", None)
    if not isinstance(mods, dict):
        mods = {}
        scenario.hypothetical_modifiers = mods
    return mods


def _expand_targets(baseline: Any, target: str) -> list[str]:
    """driver_id | constructor_id (expanded to members) | all (all drivers)."""
    drivers = scenario_drivers(baseline)
    if target == "all":
        return list(drivers)
    if target in drivers:
        return [target]
    members = [
        d for d in drivers
        if _driver_constructor(baseline, d) == target
    ]
    return members


def _driver_constructor(scenario: Any, driver_id: str) -> str:
    for d in list(getattr(scenario, "drivers", []) or []):
        did = d.get("driver_id") if isinstance(d, dict) else getattr(d, "driver_id", None)
        if str(did) == str(driver_id):
            cid = d.get("constructor_id") if isinstance(d, dict) else getattr(d, "constructor_id", "")  # noqa: E501
            return str(cid or "")
    return ""


def _apply_setup(compiled: Any, baseline: Any, iv: Intervention, trace: InterventionTrace) -> None:
    fam, op, target, param = _fam(iv), _op(iv), str(iv.target), str(iv.parameter)
    mods = _ensure_mods(compiled)
    sm = mods.get("setup")
    if not isinstance(sm, dict):
        sm = {}
        mods["setup"] = sm
    sm["enabled"] = True
    members = _expand_targets(baseline, target)
    final: dict[str, float] = {}
    for did in members:
        cur = _baseline_setup_value(baseline, did, param)
        if cur is None:
            # Fall back to Phase 20 mid-range default (documented in trace).
            try:
                from app.simulation.setup.models import SetupParameters

                cur = float(getattr(SetupParameters(), param).value)
            except Exception:
                cur = 0.0
        if op == "SET_VALUE":
            new = float(iv.value)
        else:  # ADD_DELTA
            new = float(cur) + float(iv.value)
        if target == "all":
            sm.setdefault("parameters", {})[param] = new
            trace.modifier_path = f"hypothetical_modifiers.setup.parameters.{param}"
        else:
            sm.setdefault("drivers", {}).setdefault(did, {})[param] = new
            trace.modifier_path = f"hypothetical_modifiers.setup.drivers.{did}.{param}"
        final[did] = new
    # Representative baseline/counterfactual for the trace.
    first = members[0] if members else target
    trace.baseline_value = _baseline_setup_value(baseline, first, param)
    trace.counterfactual_value = final.get(first)


def _apply_weather(compiled: Any, baseline: Any, iv: Intervention, trace: InterventionTrace) -> None:  # noqa: E501
    fam, op, target, param = _fam(iv), _op(iv), str(iv.target), str(iv.parameter)
    mods = _ensure_mods(compiled)
    if op == "DISABLE":
        mods["weather"] = {"enabled": False}
        trace.modifier_path = "hypothetical_modifiers.weather.enabled"
        trace.baseline_value = "model default (enabled)"
        trace.counterfactual_value = False
        return
    if op == "ENABLE":
        # Restore default resolution: drop any override this spec wrote earlier
        # (conflict rule forbids mixing ENABLE/DISABLE with field overrides).
        if isinstance(mods.get("weather"), dict):
            mods["weather"].pop("enabled", None)
            if not mods["weather"]:
                mods.pop("weather", None)
        trace.modifier_path = "hypothetical_modifiers.weather (default resolution)"
        trace.baseline_value = "model default"
        trace.counterfactual_value = "model default (explicitly enabled)"
        return
    cur = _baseline_weather_value(baseline, param)
    try:
        cur_f = float(cur) if cur is not None else 0.0
    except Exception:
        cur_f = 0.0
    if op == "SET_VALUE":
        new = float(iv.value)
    elif op == "ADD_DELTA":
        new = cur_f + float(iv.value)
    else:  # MULTIPLY
        new = cur_f * float(iv.value)
    wm = mods.get("weather")
    if not isinstance(wm, dict):
        wm = {}
        mods["weather"] = wm
    wm[param] = new
    trace.modifier_path = f"hypothetical_modifiers.weather.{param}"
    trace.baseline_value = cur
    trace.counterfactual_value = new


def _apply_race_control(compiled: Any, baseline: Any, iv: Intervention, trace: InterventionTrace) -> None:  # noqa: E501
    fam, op, target, param = _fam(iv), _op(iv), str(iv.target), str(iv.parameter)
    mods = _ensure_mods(compiled)
    rc = mods.get("race_control")
    if not isinstance(rc, dict):
        rc = {}
        mods["race_control"] = rc
    cur = _baseline_rc_value(baseline, param)
    if op == "DISABLE":
        rc[param] = False
        trace.counterfactual_value = False
    elif op == "ENABLE":
        rc[param] = True
        trace.counterfactual_value = True
    else:  # SET_VALUE threshold
        rc[param] = float(iv.value)
        trace.counterfactual_value = float(iv.value)
    trace.modifier_path = f"hypothetical_modifiers.race_control.{param}"
    trace.baseline_value = cur


def _apply_tyre(compiled: Any, baseline: Any, iv: Intervention, trace: InterventionTrace) -> None:
    fam, op, target, param = _fam(iv), _op(iv), str(iv.target), str(iv.parameter)
    mods = _ensure_mods(compiled)
    tm = mods.get("tyre")
    if not isinstance(tm, dict):
        tm = {}
        mods["tyre"] = tm
    members = _expand_targets(baseline, target)
    if param in ("starting_compound", "pit_compound"):
        val = str(iv.value).strip().upper()
        if target == "all":
            tm[param] = val
            trace.modifier_path = f"hypothetical_modifiers.tyre.{param}"
        else:
            node = tm.get(param)
            if not isinstance(node, dict):
                node = {}
                tm[param] = node
            node[target] = val
            trace.modifier_path = f"hypothetical_modifiers.tyre.{param}.{target}"
        trace.baseline_value = "SOFT (model default)"
        trace.counterfactual_value = val
    else:  # stints
        norm = [
            {"compound": str(s["compound"]).strip().upper(), "laps": int(s["laps"])}
            for s in iv.value
        ]
        derived_pits: list[int] = []
        cum = 0
        for s in norm[:-1]:
            cum += s["laps"]
            derived_pits.append(cum)
        node = tm.get("stints")
        if not isinstance(node, dict):
            node = {}
            tm["stints"] = node
        if target == "all":
            node["all"] = norm
            trace.modifier_path = "hypothetical_modifiers.tyre.stints.all"
        else:
            node[target] = norm
            trace.modifier_path = f"hypothetical_modifiers.tyre.stints.{target}"
        trace.baseline_value = f"model default (SOFT, pits {_default_pit_laps(total_laps_for(baseline)[0])})"  # noqa: E501
        trace.counterfactual_value = {"stints": norm, "derived_pit_laps": derived_pits}


def _apply_strategy(compiled: Any, baseline: Any, iv: Intervention, trace: InterventionTrace) -> None:  # noqa: E501
    target, param = str(iv.target), str(iv.parameter)
    mods = _ensure_mods(compiled)
    st = mods.get("strategy")
    if not isinstance(st, dict):
        st = {}
        mods["strategy"] = st
    if param == "pit_loss_seconds":
        # Phase 22 pit-loss channel: deterministic per-stop time cost (seconds).
        # Orthogonal to pit_laps; composes with any schedule. Default 0.0.
        loss = float(iv.value)
        if target == "all":
            st["pit_loss_seconds"] = loss
            trace.modifier_path = "hypothetical_modifiers.strategy.pit_loss_seconds"
        else:
            node = st.get("pit_loss_seconds")
            if not isinstance(node, dict):
                node = {}
                st["pit_loss_seconds"] = node
            node[target] = loss
            trace.modifier_path = f"hypothetical_modifiers.strategy.pit_loss_seconds.{target}"
        trace.baseline_value = 0.0
        trace.counterfactual_value = loss
        return
    pits = [int(x) for x in iv.value]
    if target == "all":
        st["pit_laps"] = pits
        trace.modifier_path = "hypothetical_modifiers.strategy.pit_laps"
    else:
        node = st.get("pit_laps")
        if not isinstance(node, dict):
            node = {}
            st["pit_laps"] = node
        node[target] = pits
        trace.modifier_path = f"hypothetical_modifiers.strategy.pit_laps.{target}"
    trace.baseline_value = f"model default (pits {_default_pit_laps(total_laps_for(baseline)[0])})"
    trace.counterfactual_value = pits


def _apply_pace(compiled: Any, baseline: Any, iv: Intervention, trace: InterventionTrace) -> None:
    fam, target = _fam(iv), str(iv.target)
    mods = _ensure_mods(compiled)
    pm = mods.get("performance")
    if not isinstance(pm, dict):
        pm = {}
        mods["performance"] = pm
    if fam == "driver":
        pm.setdefault("driver_pace_delta", {})[target] = float(iv.value)
        trace.modifier_path = f"hypothetical_modifiers.performance.driver_pace_delta.{target}"
    else:
        pm.setdefault("constructor_pace_delta", {})[target] = float(iv.value)
        trace.modifier_path = f"hypothetical_modifiers.performance.constructor_pace_delta.{target}"
    trace.baseline_value = "calibrated mean (delta semantics; see limitations)"
    trace.counterfactual_value = f"mean + ({float(iv.value)})"


_APPLIERS = {
    "setup": _apply_setup,
    "weather": _apply_weather,
    "race_control": _apply_race_control,
    "tyre": _apply_tyre,
    "strategy": _apply_strategy,
    "driver": _apply_pace,
    "car": _apply_pace,
}


def compile_spec(
    baseline: Any, spec: ScenarioSpec
) -> tuple[Any, list[InterventionTrace], list[str]]:
    """Validate + compile a spec into a NEW Scenario (baseline untouched).

    Returns (compiled_scenario, trace, warnings). Raises
    ScenarioValidationError on invalid input.
    """
    from app.simulation.scenario.registry import FAMILY_TIERS

    warnings = check_spec(spec, baseline)
    compiled = baseline.model_copy(deep=True)
    # Scenario type follows the spec (vocabulary reused from Phase 14).
    try:
        compiled.type = spec.scenario_type  # type: ignore[assignment]
    except Exception:
        pass

    trace: list[InterventionTrace] = []
    for idx, iv in enumerate(spec.interventions):
        fam = _fam(iv)
        t = InterventionTrace(
            intervention_id=iv.intervention_id or f"{spec.spec_id}-i{idx}",
            family=fam,
            op=_op(iv),
            target=str(iv.target),
            parameter=str(iv.parameter),
            affected_pathways=list(PATHWAYS.get(fam, [])),
            evidence_tier=FAMILY_TIERS.get(fam, "PRIOR_ONLY"),
        )
        applier = _APPLIERS.get(fam)
        if applier is None:  # pragma: no cover - guarded by validation
            raise ScenarioValidationError(f"no compiler for family {fam!r}")
        applier(compiled, baseline, iv, t)
        # Stamp resolved evidence + baseline into the intervention copy.
        try:
            iv.baseline_value = t.baseline_value
            iv.evidence_tier = t.evidence_tier
        except Exception:
            pass
        trace.append(t)
    return compiled, trace, warnings


def build_branch_specs(
    baseline_scenario_id: str,
    spec_id_prefix: str,
    branches: dict[str, list[Intervention]],
    scenario_type: str = "counterfactual",
    seed: int = 42,
    simulations: int = 100,
) -> list[ScenarioSpec]:
    """Build one ScenarioSpec per named branch sharing an immutable baseline."""
    specs: list[ScenarioSpec] = []
    for name, ivs in branches.items():
        specs.append(
            ScenarioSpec(
                spec_id=f"{spec_id_prefix}-{name}",
                baseline_scenario_id=baseline_scenario_id,
                scenario_type=scenario_type,  # type: ignore[arg-type]
                interventions=list(ivs),
                seed=seed,
                simulations=simulations,
            )
        )
    return specs
