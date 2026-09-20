"""Phase 21 — Modifier resolvers consumed by the vectorized simulation path.

Pit/compound schedule and pace deltas are resolved here (validating layer
above guarantees shape; these functions stay total and fail-soft to legacy
defaults so a malformed modifier can never crash a simulation).

Legacy defaults reproduced exactly when no intervention is present:
pits at laps {L: L % 20 == 0, L != total}, compound SOFT for every stint.
"""
from __future__ import annotations

from typing import Any

import numpy as np


def _mods(scenario: Any) -> dict[str, Any]:
    try:
        mods = getattr(scenario, "hypothetical_modifiers", {}) or {}
        return mods if isinstance(mods, dict) else {}
    except Exception:
        return {}


def _driver_ids(scenario: Any) -> list[str]:
    out: list[str] = []
    for d in list(getattr(scenario, "drivers", []) or []):
        if isinstance(d, dict) and d.get("driver_id"):
            out.append(str(d["driver_id"]))
    if not out:
        out = [str(x) for x in list(getattr(scenario, "grid_order", []) or [])]
    return out


def _total_laps(scenario: Any) -> int:
    try:
        laps = (getattr(scenario, "race_distance", {}) or {}).get("laps")
        if isinstance(laps, int) and laps >= 5:
            return laps
    except Exception:
        pass
    return 58


def _compound_int(name: Any) -> int:
    try:
        from app.simulation.tyre.kernels import compound_to_int

        return int(compound_to_int(str(name).strip().upper()))
    except Exception:
        return 1


def default_pit_laps(total: int) -> list[int]:
    """Legacy schedule: every 20th lap except the final lap."""
    return [lap for lap in range(1, total + 1) if lap % 20 == 0 and lap != total]


def _per_target_map(node: Any, target_all_key: str = "all") -> tuple[Any, dict[str, Any]]:
    """Split a modifier node into (global_value, per_driver_dict).

    Accepts: scalar/list global, {"all": ..., driver: ...}, or pure per-driver.
    """
    per: dict[str, Any] = {}
    glob: Any = None
    if isinstance(node, dict):
        for k, v in node.items():
            if k == target_all_key:
                glob = v
            else:
                per[str(k)] = v
    else:
        glob = node
    return glob, per


def resolve_pit_schedule(
    scenario: Any,
    driver_ids: list[str] | None = None,
    total_laps: int | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Resolve (pit_matrix, compound_matrix, info).

    pit_matrix: bool (L+1, D); compound_matrix: int8 (L+1, D) compound in
    force at each lap (1=SOFT default). Index 0 unused (laps are 1-based).
    info: {"intervened": bool, "per_driver": {did: {"pit_laps": [...],
    "compounds": [...]}}} for provenance.
    """
    driver_ids = list(driver_ids) if driver_ids else _driver_ids(scenario)
    total = int(total_laps) if total_laps else _total_laps(scenario)
    D = len(driver_ids)
    pit = np.zeros((total + 1, D), dtype=bool)
    comp = np.ones((total + 1, D), dtype=np.int8)
    info: dict[str, Any] = {"intervened": False, "per_driver": {}}

    mods = _mods(scenario)
    strat = mods.get("strategy", {}) if isinstance(mods.get("strategy"), dict) else {}
    tyre = mods.get("tyre", {}) if isinstance(mods.get("tyre"), dict) else {}

    # --- compounds ---
    start_g, start_p = _per_target_map(tyre.get("starting_compound", "SOFT"))
    pitc_g, pitc_p = _per_target_map(tyre.get("pit_compound", "SOFT"))
    stints_node = tyre.get("stints", {})
    stints_g, stints_p = (None, {}) if not isinstance(stints_node, dict) else _per_target_map(stints_node)  # noqa: E501
    strat_pl = strat.get("pit_laps", None)
    strat_g, strat_p = (None, {}) if strat_pl is None else _per_target_map(strat_pl)

    for j, did in enumerate(driver_ids):
        # Stints take precedence (compiler forbids stints + pit_laps per target).
        st_here = stints_p.get(did, stints_g)
        if isinstance(st_here, list) and st_here:
            compounds: list[int] = []
            pits_here: list[int] = []
            cum = 0
            valid = True
            for s in st_here:
                if not isinstance(s, dict):
                    valid = False
                    break
                compounds.append(_compound_int(s.get("compound", "SOFT")))
                try:
                    cum += int(s.get("laps", 0))
                except Exception:
                    valid = False
                    break
                if cum < total:
                    pits_here.append(cum)
            if not valid or cum != total:
                # Fail-soft to legacy (spec validation rejects this first).
                pits_here, compounds = default_pit_laps(total), [1]
            else:
                info["intervened"] = True
        else:
            pl_here = strat_p.get(did, strat_g)
            if pl_here is None:
                pits_here = default_pit_laps(total)
                start_only = _compound_int(
                    start_p.get(did, start_g if start_g is not None else "SOFT")
                )
                compounds = [start_only]
                if start_only != 1:
                    info["intervened"] = True
            else:
                try:
                    pits_here = sorted({int(x) for x in list(pl_here) if 2 <= int(x) <= total - 1})
                except Exception:
                    pits_here, compounds = default_pit_laps(total), [1]
                else:
                    pit_c = _compound_int(pitc_p.get(did, pitc_g if pitc_g is not None else "SOFT"))
                    start_c = _compound_int(start_p.get(did, start_g if start_g is not None else "SOFT"))  # noqa: E501
                    compounds = [start_c] + [pit_c] * len(pits_here)
                    # compounds[k] = compound IN FORCE during stint k.
                    compounds = compounds[: len(pits_here) + 1]
                    info["intervened"] = True
        # Write matrices: compound constant within a stint, switches at pit lap.
        cur = compounds[0] if compounds else 1
        pit_set = set(pits_here)
        ci = 0
        for lap in range(1, total + 1):
            if lap in pit_set:
                ci = min(ci + 1, len(compounds) - 1)
                cur = compounds[ci] if compounds else 1
                pit[lap, j] = True
            comp[lap, j] = cur
        info["per_driver"][did] = {"pit_laps": list(pits_here), "compounds": list(compounds)}
    return pit, comp, info


def resolve_pace_deltas(
    scenario: Any,
    driver_ids: list[str] | None = None,
    constructor_ids: list[str] | None = None,
) -> tuple[dict[str, float], dict[str, float]]:
    """Resolve (driver_delta, constructor_delta) maps. Empty when absent."""
    mods = _mods(scenario)
    perf = mods.get("performance", {}) if isinstance(mods.get("performance"), dict) else {}
    dd = perf.get("driver_pace_delta", {}) if isinstance(perf.get("driver_pace_delta"), dict) else {}  # noqa: E501
    cd = perf.get("constructor_pace_delta", {}) if isinstance(perf.get("constructor_pace_delta"), dict) else {}  # noqa: E501

    def _clean(m: dict[str, Any]) -> dict[str, float]:
        out: dict[str, float] = {}
        for k, v in m.items():
            try:
                if isinstance(v, bool):
                    continue
                f = float(v)
            except Exception:
                continue
            out[str(k)] = max(-3.0, min(3.0, f))
        return out

    return _clean(dd), _clean(cd)


def resolve_pit_loss(
    scenario: Any,
    driver_ids: list[str] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Resolve per-driver pit-loss seconds (Phase 22 channel).

    Returns (loss_vector, info) where loss_vector is float32 (D,) seconds
    added to a driver's cumulative race time on each of their scheduled pit
    laps, and info carries {"enabled": bool, "per_driver": {...}} provenance.

    Modifier form: hypothetical_modifiers.strategy.pit_loss_seconds is either
    a scalar (all drivers) or a mapping {"all": x, driver_id: y, ...}.
    Absent / 0.0 reproduces legacy behavior exactly (no time added).
    Fail-soft: malformed values resolve to 0.0 (validated upstream).
    """
    from app.simulation.scenario.registry import PIT_LOSS_RANGE

    driver_ids = list(driver_ids) if driver_ids else _driver_ids(scenario)
    D = len(driver_ids)
    mods = _mods(scenario)
    strat = mods.get("strategy", {}) if isinstance(mods.get("strategy"), dict) else {}
    node = strat.get("pit_loss_seconds", None)
    lo, hi = PIT_LOSS_RANGE

    def _clamp(v: Any) -> float:
        try:
            if isinstance(v, bool):
                return 0.0
            f = float(v)
        except Exception:
            return 0.0
        if not (lo <= f <= hi):
            return 0.0
        return f

    per: dict[str, float] = {}
    if isinstance(node, dict):
        glob, per_raw = _per_target_map(node)
        g = _clamp(glob) if glob is not None else 0.0
        for did in driver_ids:
            per[did] = _clamp(per_raw.get(did, g))
    elif node is None:
        for did in driver_ids:
            per[did] = 0.0
    else:
        g = _clamp(node)
        for did in driver_ids:
            per[did] = g
    vec = np.array([per.get(did, 0.0) for did in driver_ids], dtype=np.float32)
    info: dict[str, Any] = {
        "enabled": bool(np.any(vec > 0)),
        "per_driver": dict(per),
        "evidence_tier": "PRIOR_ONLY",
    }
    return vec, info
