"""Phase 21 — Baseline vs counterfactual comparison.

Only metrics the simulation actually produces are compared
(win/podium/finish/DNF/points + finish distributions + race-level exposure
counters). Distances are restricted to well-defined choices for these data:
mean/median/quantile differences and L1 distance on discrete finish
distributions. No KL (zero-probability hazards), no invented significance.
"""
from __future__ import annotations

from typing import Any

from app.simulation.scenario.models import DriverEffect, ScenarioComparison


def _quantile_from_dist(dist: dict[Any, float], q: float) -> float | None:
    """Quantile of a discrete {position: prob} distribution."""
    try:
        items = sorted((int(k), float(v)) for k, v in dist.items())
    except Exception:
        return None
    if not items:
        return None
    cum = 0.0
    for pos, p in items:
        cum += p
        if cum >= q:
            return float(pos)
    return float(items[-1][0])


def _l1_dist(a: dict[Any, float], b: dict[Any, float]) -> float:
    keys = set()
    try:
        keys = {str(k) for k in a} | {str(k) for k in b}
    except Exception:
        return 0.0
    try:
        return sum(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys)
    except Exception:
        return 0.0


def _get(drivers: dict[str, Any], did: str) -> dict[str, Any]:
    d = drivers.get(did, {})
    return d if isinstance(d, dict) else {}


def compare_results(
    spec_id: str,
    baseline_result: dict[str, Any],
    counterfactual_result: dict[str, Any],
    baseline_fp: str = "",
    counterfactual_fp: str = "",
    seed: int = 42,
    simulations: int = 0,
    evidence_tiers: dict[str, str] | None = None,
) -> ScenarioComparison:
    """Contrast two engine outputs produced with common random numbers."""
    b_drivers = baseline_result.get("drivers", {}) or {}
    c_drivers = counterfactual_result.get("drivers", {}) or {}
    driver_ids = sorted(set(b_drivers) | set(c_drivers))

    effects: list[DriverEffect] = []
    for did in driver_ids:
        b = _get(b_drivers, did)
        c = _get(c_drivers, did)
        b_dist = b.get("finish_distribution", {}) or {}
        c_dist = c.get("finish_distribution", {}) or {}
        b_win = float(b.get("win_probability", 0.0) or 0.0)
        c_win = float(c.get("win_probability", 0.0) or 0.0)
        effects.append(
            DriverEffect(
                driver_id=did,
                d_win_probability=c_win - b_win,
                d_podium_probability=float(c.get("podium_probability", 0.0) or 0.0)
                - float(b.get("podium_probability", 0.0) or 0.0),
                d_expected_finish=float(c.get("expected_finish", 0.0) or 0.0)
                - float(b.get("expected_finish", 0.0) or 0.0),
                d_median_finish=float(c.get("median_finish", 0.0) or 0.0)
                - float(b.get("median_finish", 0.0) or 0.0),
                d_dnf_probability=float(c.get("dnf_probability", 0.0) or 0.0)
                - float(b.get("dnf_probability", 0.0) or 0.0),
                d_expected_points=float(c.get("expected_points", 0.0) or 0.0)
                - float(b.get("expected_points", 0.0) or 0.0),
                l1_finish_distribution=_l1_dist(b_dist, c_dist),
                d_quantile_25=(lambda a, x: (a - x) if a is not None and x is not None else 0.0)(
                    _quantile_from_dist(c_dist, 0.25), _quantile_from_dist(b_dist, 0.25)
                ),
                d_quantile_50=(lambda a, x: (a - x) if a is not None and x is not None else 0.0)(
                    _quantile_from_dist(c_dist, 0.50), _quantile_from_dist(b_dist, 0.50)
                ),
                d_quantile_75=(lambda a, x: (a - x) if a is not None and x is not None else 0.0)(
                    _quantile_from_dist(c_dist, 0.75), _quantile_from_dist(b_dist, 0.75)
                ),
                baseline_win_probability=b_win,
                counterfactual_win_probability=c_win,
            )
        )

    # Constructors (sums already in results; contrast them).
    b_cons = baseline_result.get("constructors", {}) or {}
    c_cons = counterfactual_result.get("constructors", {}) or {}
    cons_effects: dict[str, dict[str, float]] = {}
    for cid in sorted(set(b_cons) | set(c_cons)):
        bb = b_cons.get(cid, {}) if isinstance(b_cons.get(cid), dict) else {}
        cc = c_cons.get(cid, {}) if isinstance(c_cons.get(cid), dict) else {}
        cons_effects[str(cid)] = {
            "d_win_probability": float(cc.get("win_probability", 0.0) or 0.0)
            - float(bb.get("win_probability", 0.0) or 0.0),
            "d_podium_probability": float(cc.get("podium_probability", 0.0) or 0.0)
            - float(bb.get("podium_probability", 0.0) or 0.0),
        }

    # Race-level exposure counters actually produced by the engines.
    race_effects: dict[str, Any] = {}
    for key in ("race_control", "weather"):
        bb = baseline_result.get(key, {}) if isinstance(baseline_result.get(key), dict) else {}
        cc = counterfactual_result.get(key, {}) if isinstance(counterfactual_result.get(key), dict) else {}  # noqa: E501
        entry: dict[str, Any] = {"baseline": {}, "counterfactual": {}, "delta": {}}
        for metric in (
            "vsc_count", "sc_count", "red_count", "yellow_count",
            "double_yellow_count", "restart_count",
            "mean_wetness", "max_wetness", "mean_rainfall",
        ):
            if metric in bb or metric in cc:
                try:
                    bv = float(bb.get(metric, 0.0) or 0.0)
                    cv = float(cc.get(metric, 0.0) or 0.0)
                except Exception:
                    continue
                entry["baseline"][metric] = bv
                entry["counterfactual"][metric] = cv
                entry["delta"][metric] = cv - bv
        if entry["delta"]:
            race_effects[key] = entry
    # Setup offsets actually applied (from setup blocks when present).
    for label, res in (("baseline", baseline_result), ("counterfactual", counterfactual_result)):
        sm = res.get("setup_model", res.get("setup", {}))
        if isinstance(sm, dict) and sm.get("offsets_sec_per_lap"):
            race_effects.setdefault("setup", {})[label] = dict(sm["offsets_sec_per_lap"])

    notes = [
        "Deltas are counterfactual minus baseline under common random numbers "
        "(same seed); residual Monte Carlo noise scales ~1/sqrt(N).",
        "No significance testing is performed; no causal identification claimed.",
        "Pit stops carry no time loss in the vectorized model: extra stops show "
        "only tyre-freshness benefit (see explanation assumptions).",
    ]
    return ScenarioComparison(
        spec_id=spec_id,
        baseline_fingerprint=baseline_fp,
        counterfactual_fingerprint=counterfactual_fp,
        seed=seed,
        simulations=simulations or int(baseline_result.get("simulations", 0) or 0),
        common_random_numbers=True,
        driver_effects=effects,
        constructor_effects=cons_effects,
        race_effects=race_effects,
        evidence_tiers=dict(evidence_tiers or {}),
        metric_notes=notes,
    )
