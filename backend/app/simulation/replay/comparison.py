"""Phase 22 — Extended distribution comparison.

Builds on the Phase 21 comparison (win/podium/finish/DNF/points + L1 +
quartiles) with top-10 probability, P10/P90 quantiles, absolute + relative
differences, schedule-derived pit counts, and an explicit unmeasurable map
for quantities the engine does not emit (mean lap time, total race time,
tyre degradation traces, position trajectories) — reported as
NOT_TESTABLE, never invented.
"""
from __future__ import annotations

from typing import Any

from app.simulation.replay.models import ExtendedComparison, ExtendedDriverDelta
from app.simulation.scenario.comparison import (
    _l1_dist,
    _quantile_from_dist,
)


def _get(drivers: dict[str, Any], did: str) -> dict[str, Any]:
    d = drivers.get(did, {})
    return d if isinstance(d, dict) else {}


def _rel(new: float, old: float) -> float | None:
    try:
        if old == 0:
            return None
        return (new - old) / abs(old)
    except Exception:
        return None


def extended_compare(
    spec_id: str,
    experiment_id: str,
    baseline_result: dict[str, Any],
    counterfactual_result: dict[str, Any],
    baseline_fp: str = "",
    counterfactual_fp: str = "",
    seed: int = 42,
    simulations: int = 0,
    evidence_tiers: dict[str, str] | None = None,
    baseline_scenario: Any = None,
    counterfactual_scenario: Any = None,
) -> ExtendedComparison:
    b_drivers = baseline_result.get("drivers", {}) or {}
    c_drivers = counterfactual_result.get("drivers", {}) or {}
    driver_ids = sorted(set(b_drivers) | set(c_drivers))
    deltas: list[ExtendedDriverDelta] = []
    for did in driver_ids:
        b = _get(b_drivers, did)
        c = _get(c_drivers, did)
        b_dist = b.get("finish_distribution", {}) or {}
        c_dist = c.get("finish_distribution", {}) or {}
        b_win = float(b.get("win_probability", 0.0) or 0.0)
        c_win = float(c.get("win_probability", 0.0) or 0.0)

        def _dq(q: float) -> float:
            a = _quantile_from_dist(c_dist, q)
            x = _quantile_from_dist(b_dist, q)
            if a is None or x is None:
                return 0.0
            return float(a) - float(x)

        deltas.append(ExtendedDriverDelta(
            driver_id=did,
            d_win_probability=c_win - b_win,
            d_podium_probability=float(c.get("podium_probability", 0.0) or 0.0)
            - float(b.get("podium_probability", 0.0) or 0.0),
            d_top10_probability=float(c.get("top10_probability", 0.0) or 0.0)
            - float(b.get("top10_probability", 0.0) or 0.0),
            d_expected_finish=float(c.get("expected_finish", 0.0) or 0.0)
            - float(b.get("expected_finish", 0.0) or 0.0),
            d_median_finish=float(c.get("median_finish", 0.0) or 0.0)
            - float(b.get("median_finish", 0.0) or 0.0),
            d_dnf_probability=float(c.get("dnf_probability", 0.0) or 0.0)
            - float(b.get("dnf_probability", 0.0) or 0.0),
            d_expected_points=float(c.get("expected_points", 0.0) or 0.0)
            - float(b.get("expected_points", 0.0) or 0.0),
            d_quantile_10=_dq(0.10),
            d_quantile_25=_dq(0.25),
            d_quantile_50=_dq(0.50),
            d_quantile_75=_dq(0.75),
            d_quantile_90=_dq(0.90),
            l1_finish_distribution=_l1_dist(b_dist, c_dist),
            relative_win_delta=_rel(c_win, b_win),
            baseline_win_probability=b_win,
            counterfactual_win_probability=c_win,
        ))

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
    for label, res in (("baseline", baseline_result), ("counterfactual", counterfactual_result)):
        sm = res.get("setup_model", res.get("setup", {}))
        if isinstance(sm, dict) and sm.get("offsets_sec_per_lap"):
            race_effects.setdefault("setup", {})[label] = dict(sm["offsets_sec_per_lap"])
        pl = res.get("pit_loss", {})
        if isinstance(pl, dict) and pl.get("enabled"):
            race_effects.setdefault("pit_loss", {})[label] = dict(pl.get("seconds_per_stop", {}))

    # Schedule-derived pit counts (identifiable from the schedule matrices;
    # actual historical pit counts are NON_IDENTIFIABLE unless canonical
    # pit data exists for the race).
    pit_counts: dict[str, Any] = {"evidence_tier": "PRIOR_ONLY", "per_driver": {}}
    try:
        from app.simulation.scenario.resolvers import resolve_pit_schedule

        for label, scen in (("baseline", baseline_scenario), ("counterfactual", counterfactual_scenario)):  # noqa: E501
            if scen is None:
                continue
            laps = int((getattr(scen, "race_distance", {}) or {}).get("laps") or 58)
            drivers = [d["driver_id"] for d in (getattr(scen, "drivers", []) or []) if isinstance(d, dict)]  # noqa: E501
            pit_mat, _, _ = resolve_pit_schedule(scen, drivers, laps)
            pit_counts["per_driver"][label] = {
                did: int(pit_mat[1:, j].sum()) for j, did in enumerate(drivers)
            }
        bpc = pit_counts["per_driver"].get("baseline", {})
        cpc = pit_counts["per_driver"].get("counterfactual", {})
        pit_counts["delta"] = {
            did: int(cpc.get(did, 0)) - int(bpc.get(did, 0)) for did in set(bpc) | set(cpc)
        }
    except Exception as exc:
        pit_counts = {"evidence_tier": "NOT_TESTABLE", "error": str(exc)}

    unmeasurable = {
        "mean_lap_time": "NOT_TESTABLE",
        "total_race_time": "NOT_TESTABLE",
        "tyre_degradation_trace": "NOT_TESTABLE",
        "position_trajectory": "NOT_TESTABLE",
        "pit_stop_time_loss_observed": "NON_IDENTIFIABLE",
    }
    notes = [
        "Deltas are counterfactual minus baseline under common random numbers "
        "(same seed); residual Monte Carlo noise scales ~1/sqrt(N).",
        "Relative win deltas are None when the baseline probability is zero "
        "(division undefined); absolute deltas always reported.",
        "No significance testing is performed; no causal identification claimed.",
        "Mean/total lap-time and degradation-trace contrasts are NOT_TESTABLE: "
        "the engine emits finish distributions, not lap-time aggregates.",
    ]
    return ExtendedComparison(
        spec_id=spec_id,
        experiment_id=experiment_id,
        baseline_fingerprint=baseline_fp,
        counterfactual_fingerprint=counterfactual_fp,
        seed=seed,
        simulations=simulations or int(baseline_result.get("simulations", 0) or 0),
        common_random_numbers=True,
        driver_deltas=deltas,
        race_effects=race_effects,
        pit_counts=pit_counts,
        unmeasurable=unmeasurable,
        evidence_tiers=dict(evidence_tiers or {}),
        metric_notes=notes,
    )
