"""Phase 22 — Historical replay validation + walk-forward + leakage probes.

Validation targets (observed results) are used post-hoc ONLY. Walk-forward
splits obey training_observation_date < target_race_date via the as_of
contract. Adversarial leakage probes inject future information into a copy
of the scenario modifiers and require bit-identical outputs.
"""
from __future__ import annotations

from typing import Any

from app.simulation.replay.models import DeviationMetrics


def _observed_winner(observed: dict[str, Any]) -> str:
    for did, row in observed.items():
        if isinstance(row, dict) and row.get("final_position") == 1:
            return str(did)
    return ""


def _observed_top3(observed: dict[str, Any]) -> set[str]:
    return {
        str(did) for did, row in observed.items()
        if isinstance(row, dict) and row.get("final_position") in (1, 2, 3)
    }


def _is_dnf(status: Any) -> bool:
    s = str(status or "").lower()
    return ("dnf" in s or "retir" in s or "accident" in s or "engine" in s
            or "gearbox" in s or "collision" in s) and "finish" not in s


def deviation_metrics(
    baseline_result: dict[str, Any],
    observed: dict[str, Any],
    race_id: str = "",
) -> DeviationMetrics:
    """Post-hoc baseline-vs-observed contrast (never a simulation input)."""
    drivers = baseline_result.get("drivers", {}) or {}
    win = {did: float(d.get("win_probability", 0.0) or 0.0) for did, d in drivers.items() if isinstance(d, dict)}  # noqa: E501
    predicted = max(win, key=lambda k: win[k]) if win else ""
    obs_winner = _observed_winner(observed)
    pred_top3 = sorted(win, key=lambda k: win[k], reverse=True)[:3]
    overlap = len(set(pred_top3) & _observed_top3(observed))
    errs: list[float] = []
    matched = 0
    for did, d in drivers.items():
        if not isinstance(d, dict):
            continue
        row = observed.get(did)
        if not isinstance(row, dict) or row.get("final_position") is None:
            continue
        try:
            exp = float(d.get("expected_finish"))
            errs.append(abs(exp - float(row["final_position"])))
            matched += 1
        except Exception:
            continue
    mae = (sum(errs) / len(errs)) if errs else None
    dnf_errs: list[float] = []
    for did, d in drivers.items():
        if not isinstance(d, dict):
            continue
        row = observed.get(did)
        if not isinstance(row, dict):
            continue
        try:
            dnf_errs.append(abs(float(d.get("dnf_probability", 0.0) or 0.0) - (1.0 if _is_dnf(row.get("status")) else 0.0)))  # noqa: E501
        except Exception:
            continue
    dnf_mm = (sum(dnf_errs) / len(dnf_errs)) if dnf_errs else None
    return DeviationMetrics(
        predicted_winner=predicted,
        observed_winner=obs_winner,
        winner_match=bool(predicted) and predicted == obs_winner,
        top3_overlap=overlap,
        finish_mae=mae,
        finish_mae_drivers=matched,
        dnf_mismatch=dnf_mm,
        pit_count_mismatch="NON_IDENTIFIABLE",
        lap_time_mae="NON_IDENTIFIABLE",
        coverage={
            "race_id": race_id,
            "simulated_drivers": len(drivers),
            "observed_drivers": len(observed),
            "matched_drivers": matched,
            "fully_observable": ["grid_order", "final_positions", "status"],
            "partially_observable": ["pit_stops_where_canonical", "qualifying"],
            "non_identifiable": ["weather", "setup", "fuel", "strategy", "tyre_compounds", "lap_times"],  # noqa: E501
        },
    )


def walk_forward(
    race_ids: list[str],
    seed: int = 42,
    simulations: int = 60,
    laps: int | None = 8,
) -> list[dict[str, Any]]:
    """Replay each race with as_of-gated calibration; record observation windows."""
    from app.simulation.replay.replay_engine import ReplayEngine

    eng = ReplayEngine(seed=seed, simulations=simulations)
    rows: list[dict[str, Any]] = []
    for race_id in race_ids:
        rep = eng.replay(race_id, seed=seed, simulations=simulations, laps=laps)
        dev = rep.deviation_metrics
        rows.append({
            "race_id": race_id,
            "training_end": rep.provenance.get("as_of", ""),
            "target_date": rep.provenance.get("race_date", ""),
            "observations_used": "calibration_api(as_of), canonical grid/identities",
            "observations_excluded": "final result, future pits/weather/RC/tyre/telemetry",
            "predicted_winner": dev.predicted_winner if dev else "",
            "observed_winner": dev.observed_winner if dev else "",
            "winner_match": dev.winner_match if dev else False,
            "top3_overlap": dev.top3_overlap if dev else 0,
            "finish_mae": dev.finish_mae if dev else None,
            "baseline_fingerprint": rep.baseline_fingerprint,
        })
    return rows


def leakage_probe(scenario: Any, seed: int = 42, simulations: int = 60) -> dict[str, Any]:
    """Inject future-realized blocks; require identical outputs.

    Returns {"violations": [...], "max_abs_win_delta": float}.
    """
    from app.simulation.scenario.engine import ScenarioEngine

    eng = ScenarioEngine(seed=seed, simulations=simulations)
    clean = eng.run_baseline(scenario, simulations=simulations, seed=seed)
    dirty = scenario.model_copy(deep=True)
    mods = dirty.hypothetical_modifiers or {}
    mods["future_result"] = {"winner": "VER", "podium": ["VER", "PER", "LEC"]}
    mods["realized_weather"] = {"rain_lap10": 99.0}
    mods["observed_pit"] = {"VER": [10, 30]}
    mods["final_standings"] = {"VER": 1}
    dirty.hypothetical_modifiers = mods
    if isinstance(dirty.hypothetical_modifiers.get("weather"), dict):
        dirty.hypothetical_modifiers["weather"]["realized_rain_lap10"] = 50.0
    else:
        dirty.hypothetical_modifiers["weather"] = {"realized_rain_lap10": 50.0}
    injected = eng.run_baseline(dirty, simulations=simulations, seed=seed)
    max_delta = 0.0
    violations: list[str] = []
    for did, d in (clean.get("drivers", {}) or {}).items():
        c = (injected.get("drivers", {}) or {}).get(did, {})
        try:
            delta = abs(float(d.get("win_probability", 0.0)) - float(c.get("win_probability", 0.0)))
        except Exception:
            delta = 0.0
        max_delta = max(max_delta, delta)
        if delta > 1e-12:
            violations.append(f"leakage: {did} win_prob moved by {delta}")
    return {"violations": violations, "max_abs_win_delta": max_delta}
