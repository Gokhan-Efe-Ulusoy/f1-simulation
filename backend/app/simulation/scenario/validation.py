"""Phase 21 — Scenario validation (reject invalid before execution).

Every failure returns a message identifying the exact problem. The compiler
raises ScenarioValidationError; tests may also inspect messages directly.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.simulation.scenario.models import Intervention, ScenarioSpec
from app.simulation.scenario.registry import (
    FAMILY_OPS,
    FAMILY_PARAMS,
    FAMILY_TIERS,
    LEAKAGE_SUBSTRINGS,
    PACE_DELTA_MAX,
    PACE_DELTA_MIN,
    RC_THRESHOLDS,
    TYRE_COMPOUNDS,
    WEATHER_FIELDS,
    era_support,
    is_leakage_param,
)


class ScenarioValidationError(ValueError):
    """Raised when a spec or intervention is invalid."""


# Families whose target must be a driver / constructor / race-wide.
DRIVER_SCOPED = ("setup", "strategy", "tyre", "driver")
CONSTRUCTOR_SCOPED = ("car",)
RACE_SCOPED = ("race_control", "weather")


def _fam(iv: Intervention) -> str:
    return iv.family.value if hasattr(iv.family, "value") else str(iv.family)


def _op(iv: Intervention) -> str:
    return iv.op.value if hasattr(iv.op, "value") else str(iv.op)


def scenario_drivers(scenario: Any) -> list[str]:
    out: list[str] = []
    for d in list(getattr(scenario, "drivers", []) or []):
        if isinstance(d, dict) and d.get("driver_id"):
            out.append(str(d["driver_id"]))
        elif getattr(d, "driver_id", None):
            out.append(str(d.driver_id))
    if not out:
        out = [str(x) for x in list(getattr(scenario, "grid_order", []) or [])]
    return out


def scenario_constructors(scenario: Any) -> list[str]:
    out: list[str] = []
    for d in list(getattr(scenario, "drivers", []) or []):
        cid = d.get("constructor_id") if isinstance(d, dict) else getattr(d, "constructor_id", "")
        if cid:
            out.append(str(cid))
    return sorted(set(out))


def total_laps_for(scenario: Any) -> tuple[int, bool]:
    """Return (laps, fell_back_to_default). Mirrors vectorized default (58)."""
    try:
        laps = (getattr(scenario, "race_distance", {}) or {}).get("laps")
        if isinstance(laps, int) and laps >= 5:
            return laps, False
    except Exception:
        pass
    return 58, True


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate_intervention(
    iv: Intervention, baseline: Any
) -> tuple[list[str], list[str], dict[str, Any]]:
    """Validate one intervention. Returns (errors, warnings, context).

    Context carries resolved helpers for the compiler (e.g. total laps,
    era status) so work is not repeated.
    """
    errors: list[str] = []
    warnings: list[str] = []
    ctx: dict[str, Any] = {}
    fam = _fam(iv)
    op = _op(iv)
    param = str(iv.parameter)
    target = str(iv.target)

    # --- family / op / parameter vocabulary ---
    if fam not in FAMILY_OPS:
        return [f"unknown intervention family: {fam!r}"], warnings, ctx
    if op not in FAMILY_OPS[fam]:
        errors.append(f"op {op!r} not allowed for family {fam!r} (allowed: {FAMILY_OPS[fam]})")
    if param not in FAMILY_PARAMS.get(fam, ()):
        if is_leakage_param(param):
            errors.append(
                f"parameter {param!r} rejected: would inject realized/future "
                f"information or target structural scenario state"
            )
        else:
            errors.append(f"unknown parameter {param!r} for family {fam!r}")
        return errors, warnings, ctx
    if is_leakage_param(param):
        errors.append(f"parameter {param!r} rejected: leakage blocklist")
        return errors, warnings, ctx

    # --- target scope ---
    drivers = scenario_drivers(baseline)
    constructors = scenario_constructors(baseline)
    if fam in DRIVER_SCOPED:
        if target == "all":
            pass
        elif fam == "driver" and target not in drivers:
            errors.append(f"unknown driver target {target!r} (scenario has {len(drivers)} drivers)")
        elif fam in ("setup", "strategy", "tyre") and target not in drivers and target != "all":
            # constructor expansion allowed for these families
            if target not in constructors:
                errors.append(
                    f"unknown target {target!r} for family {fam!r}: "
                    f"expected driver_id, constructor_id, or 'all'"
                )
            else:
                ctx["expand_constructor"] = True
    elif fam in CONSTRUCTOR_SCOPED:
        if target not in constructors:
            errors.append(f"unknown constructor target {target!r} (scenario has {constructors})")
    elif fam in RACE_SCOPED:
        if target not in ("race", "all"):
            errors.append(f"family {fam!r} is race-wide: target must be 'race' or 'all', got {target!r}")  # noqa: E501

    # --- value checks per family ---
    total, fell_back = total_laps_for(baseline)
    ctx["total_laps"] = total
    if fell_back:
        warnings.append("race_distance.laps missing; using model default 58 for bounds")

    if fam == "setup":
        if not _is_num(iv.value):
            errors.append(f"setup.{param} requires numeric value, got {type(iv.value).__name__}")
        else:
            # Bounds via Phase 20 era constraints (no new bounds invented).
            try:
                from app.simulation.setup.models import get_era_constraints
                from app.simulation.scenario.registry import era_for_season

                era = era_for_season(getattr(baseline, "season_id", "2024"))
                cons = get_era_constraints(era).parameters.get(param, {})
                lo, hi = cons.get("minimum"), cons.get("maximum")
                if op == "SET_VALUE" and lo is not None and hi is not None:
                    if not (lo <= float(iv.value) <= hi):
                        errors.append(
                            f"setup.{param}={iv.value} out of model bounds [{lo}, {hi}] (era {era})"
                        )
                if op == "ADD_DELTA":
                    # resolve current value from baseline setup state
                    try:
                        from app.simulation.setup.offsets import setup_states_for_scenario

                        states = setup_states_for_scenario(baseline)
                        members = (
                            [target] if target in drivers
                            else [d for d in drivers if _driver_constructor(baseline, d) == target]
                            if target in constructors else list(states.keys())
                        )
                        for did in members:
                            st = states.get(did)
                            if st is None:
                                continue
                            cur = getattr(st.parameters, param).value
                            new = float(cur) + float(iv.value)
                            if lo is not None and hi is not None and not (lo <= new <= hi):
                                errors.append(
                                    f"setup.{param} delta {iv.value} on {did} would leave "
                                    f"bounds [{lo}, {hi}] ({cur} -> {new})"
                                )
                                break
                    except ScenarioValidationError:
                        raise
                    except Exception as e:
                        warnings.append(f"could not resolve baseline setup value: {e}")
            except ScenarioValidationError:
                raise
            except Exception as e:
                warnings.append(f"setup bounds check skipped: {e}")

    elif fam == "weather":
        if op in ("ENABLE", "DISABLE"):
            if param != "enabled":
                errors.append("weather ENABLE/DISABLE only supports parameter 'enabled'")
            if iv.value is not None and not isinstance(iv.value, bool):
                errors.append("weather ENABLE/DISABLE takes no value (must be null)")
        else:
            if not _is_num(iv.value):
                errors.append(f"weather.{param} requires numeric value")
            else:
                lo, hi = WEATHER_FIELDS[param]
                if op == "SET_VALUE" and not (lo <= float(iv.value) <= hi):
                    errors.append(f"weather.{param}={iv.value} out of range [{lo}, {hi}]")
                # ADD_DELTA / MULTIPLY re-validated at compile time against baseline.

    elif fam == "race_control":
        if op in ("ENABLE", "DISABLE"):
            from app.simulation.scenario.registry import RC_FLAGS

            if param not in RC_FLAGS:
                errors.append(f"race_control ENABLE/DISABLE unknown flag {param!r}")
            if iv.value is not None and not isinstance(iv.value, bool):
                errors.append("race_control ENABLE/DISABLE takes no value (must be null)")
        else:  # SET_VALUE on thresholds
            if param not in RC_THRESHOLDS:
                errors.append(
                    f"race_control.{param} is not settable: only {sorted(RC_THRESHOLDS)} "
                    f"are honoured by the vectorized path (forced events UNSUPPORTED)"
                )
            elif not _is_num(iv.value):
                errors.append(f"race_control.{param} requires numeric value")
            else:
                lo, hi = RC_THRESHOLDS[param]
                if not (lo <= float(iv.value) <= hi):
                    errors.append(f"race_control.{param}={iv.value} out of range [{lo}, {hi}]")

    elif fam == "tyre":
        if param in ("starting_compound", "pit_compound"):
            if not isinstance(iv.value, str) or iv.value.strip().upper() not in TYRE_COMPOUNDS:
                errors.append(
                    f"tyre.{param} must be one of {list(TYRE_COMPOUNDS)}, got {iv.value!r}"
                )
        elif param == "stints":
            errors.extend(_check_stints(iv.value, total))

    elif fam == "strategy":
        if param == "pit_loss_seconds":
            # Phase 22 pit-loss channel: orthogonal to pit_laps (no conflict).
            from app.simulation.scenario.registry import PIT_LOSS_RANGE

            if not _is_num(iv.value):
                errors.append("strategy.pit_loss_seconds requires a numeric value (seconds)")
            else:
                lo, hi = PIT_LOSS_RANGE
                if not (lo <= float(iv.value) <= hi):
                    errors.append(
                        f"strategy.pit_loss_seconds={iv.value} out of model bounds "
                        f"[{lo}, {hi}] seconds"
                    )
        elif param == "pit_laps":
            if not isinstance(iv.value, list) or not iv.value:
                errors.append("strategy.pit_laps requires a non-empty list of lap numbers")
            elif not all(isinstance(x, int) and not isinstance(x, bool) for x in iv.value):
                errors.append("strategy.pit_laps must be a list of integers")
            elif sorted(iv.value) != list(iv.value) or len(set(iv.value)) != len(iv.value):
                errors.append("strategy.pit_laps must be strictly increasing with no repeats")
            elif any(x < 2 or x > total - 1 for x in iv.value):
                errors.append(
                    f"strategy.pit_laps {iv.value} out of race bounds [2, {total - 1}]"
                )

    elif fam in ("driver", "car"):
        if param != "pace_delta":
            errors.append(f"unknown parameter {param!r} for family {fam!r}")
        elif not _is_num(iv.value):
            errors.append(f"{fam}.pace_delta requires numeric value")
        elif not (PACE_DELTA_MIN <= float(iv.value) <= PACE_DELTA_MAX):
            errors.append(
                f"{fam}.pace_delta={iv.value} out of model bounds "
                f"[{PACE_DELTA_MIN}, {PACE_DELTA_MAX}]"
            )

    # --- era note (never a silent upgrade; UNKNOWN allowed + flagged) ---
    try:
        status, note = era_support(fam, getattr(baseline, "season_id", "2024"))
    except Exception:
        status, note = "SUPPORTED", ""
    ctx["era_status"] = status
    ctx["era_note"] = note
    if status == "UNKNOWN":
        warnings.append(note)
    # Tyre mechanism unavailable pre-2023 in the vectorized path → honest no-op note.
    if fam in ("tyre", "strategy"):
        try:
            season = int(str(getattr(baseline, "season_id", "2024"))[:4])
        except Exception:
            season = 2024
        if season < 2023:
            warnings.append(
                f"{fam} intervention on a pre-2023 season: the vectorized tyre model "
                f"is inactive for this era, so pit/compound changes have no pace effect "
                f"(still recorded in provenance)."
            )

    # --- evidence tier (compiler stamps; never upgraded by Monte Carlo) ---
    ctx["evidence_tier"] = FAMILY_TIERS.get(fam, "PRIOR_ONLY")
    return errors, warnings, ctx


def _check_stints(value: Any, total: int) -> list[str]:
    if not isinstance(value, list) or not value:
        return ["tyre.stints requires a non-empty list of {compound, laps}"]
    errs: list[str] = []
    total_laps = 0
    for i, s in enumerate(value):
        if not isinstance(s, dict):
            return [f"tyre.stints[{i}] must be {{compound, laps}}"]
        c = str(s.get("compound", "")).upper()
        if c not in TYRE_COMPOUNDS:
            errs.append(f"tyre.stints[{i}].compound must be one of {list(TYRE_COMPOUNDS)}")
        laps = s.get("laps")
        if not isinstance(laps, int) or isinstance(laps, bool) or laps < 1:
            errs.append(f"tyre.stints[{i}].laps must be a positive integer")
        else:
            total_laps += laps
    if not errs and total_laps != total:
        errs.append(
            f"tyre.stints lap total {total_laps} must equal race laps {total} "
            f"(pit_laps form allows partial schedules instead)"
        )
    return errs


def _driver_constructor(scenario: Any, driver_id: str) -> str:
    for d in list(getattr(scenario, "drivers", []) or []):
        did = d.get("driver_id") if isinstance(d, dict) else getattr(d, "driver_id", None)
        if str(did) == str(driver_id):
            cid = d.get("constructor_id") if isinstance(d, dict) else getattr(d, "constructor_id", "")  # noqa: E501
            return str(cid or "")
    return ""


def validate_spec(spec: ScenarioSpec, baseline: Any) -> tuple[list[str], list[str]]:
    """Validate a whole spec: baseline integrity + per-intervention + conflicts."""
    errors: list[str] = []
    warnings: list[str] = []

    # --- baseline integrity ---
    if getattr(baseline, "scenario_id", "") != spec.baseline_scenario_id:
        errors.append(
            f"spec baseline {spec.baseline_scenario_id!r} does not match "
            f"scenario {getattr(baseline, 'scenario_id', '')!r}"
        )
    # Temporal gate: as_of must be strictly before race date (repo rule).
    try:
        from app.simulation.scenario_v14 import TemporalContext

        as_of = getattr(baseline, "as_of", "") or ""
        date = getattr(baseline, "date", "") or ""
        if as_of and date:
            if TemporalContext(as_of=as_of).is_allowed(date):
                errors.append(
                    f"baseline violates temporal gate: as_of {as_of!r} is not "
                    f"strictly before race date {date!r}"
                )
    except ScenarioValidationError:
        raise
    except Exception as e:
        warnings.append(f"temporal gate check skipped: {e}")

    if spec.scenario_type not in ("historical", "counterfactual", "hypothetical", "future"):
        errors.append(f"unknown scenario_type {spec.scenario_type!r}")

    # --- per-intervention ---
    seen: dict[tuple[str, str, str], int] = {}
    has_pit: set[str] = set()
    has_stints: set[str] = set()
    for idx, iv in enumerate(spec.interventions):
        errs, warns, _ = validate_intervention(iv, baseline)
        errors.extend(f"[intervention {idx}] {e}" for e in errs)
        warnings.extend(f"[intervention {idx}] {w}" for w in warns)
        try:
            key = iv.key()
        except Exception:
            continue
        if key in seen:
            errors.append(
                f"[intervention {idx}] conflicting intervention: same "
                f"(family, target, parameter) as intervention {seen[key]}"
            )
        else:
            seen[key] = idx
        fam = iv.family.value if hasattr(iv.family, "value") else str(iv.family)
        param = str(iv.parameter)
        if fam == "strategy" and param == "pit_laps":
            has_pit.add(str(iv.target))
        if fam == "tyre" and param == "stints":
            has_stints.add(str(iv.target))
    for t in has_pit & has_stints:
        errors.append(
            f"conflicting interventions for target {t!r}: both strategy.pit_laps "
            f"and tyre.stints (use one schedule form)"
        )
    # Weather ENABLE/DISABLE must stand alone (it selects default resolution).
    weather_flag_ops = [
        (idx, iv) for idx, iv in enumerate(spec.interventions)
        if (_fam(iv) == "weather" and _op(iv) in ("ENABLE", "DISABLE"))
    ]
    weather_field_ops = [
        idx for idx, iv in enumerate(spec.interventions)
        if (_fam(iv) == "weather" and _op(iv) not in ("ENABLE", "DISABLE"))
    ]
    if weather_flag_ops and weather_field_ops:
        errors.append(
            "conflicting weather interventions: ENABLE/DISABLE must stand alone, "
            "not combined with field overrides"
        )
    return errors, warnings


def _fam(iv: Intervention) -> str:
    return iv.family.value if hasattr(iv.family, "value") else str(iv.family)


def _op(iv: Intervention) -> str:
    return iv.op.value if hasattr(iv.op, "value") else str(iv.op)


def check_spec(spec: ScenarioSpec, baseline: Any) -> list[str]:
    """Validate and return warnings, raising on errors."""
    errors, warnings = validate_spec(spec, baseline)
    if errors:
        raise ScenarioValidationError("; ".join(errors))
    return warnings
