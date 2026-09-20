"""Phase 28 — Strategy service (thin wrapper over DecisionEngine)."""

from __future__ import annotations

from typing import Any

from app.simulation.strategy.decision_engine import DecisionEngine
from app.simulation.strategy.state import StrategyState


def evaluate_strategy(
    state_dict: dict[str, Any], track_pit_loss: float = 22.0, seed: int | None = None
) -> dict[str, Any]:
    # state_dict is expected to be a StrategyState-like payload from client
    # Build StrategyState via Pydantic validation (no leakage fields allowed)
    # Reject future_* fields if present
    leakage_keys = [
        k
        for k in state_dict.keys()
        if "future" in k.lower() or "observed_result" in k.lower() or "actual_" in k.lower()
    ]
    if leakage_keys:
        raise ValueError(f"leakage fields rejected: {leakage_keys}")

    try:
        state = StrategyState.model_validate(state_dict)
    except Exception as e:
        raise ValueError(f"invalid StrategyState: {e}") from e

    if not (0 <= track_pit_loss <= 60):
        raise ValueError("track_pit_loss must be 0..60")

    seed_val = int(seed) if seed is not None else 42
    engine = DecisionEngine(as_of="2024-03-01", seed=seed_val)
    out = engine.decide(state, track_pit_loss=track_pit_loss, seed=seed_val)
    data = out.model_dump() if hasattr(out, "model_dump") else dict(out)  # type: ignore[attr-defined]  # noqa: E501

    return {
        "driver_id": state.driver_id,
        "lap": state.lap,
        "recommended_action": data.get("chosen_action"),
        "decision": data.get("decision"),
        "target_compound": data.get("target_compound"),
        "pit_window": data.get("pit_window"),
        "candidate_actions": data.get("candidate_actions"),
        "evaluations": data.get("evaluations"),
        "estimated_effect": {
            "expected_race_time": (data.get("evaluations") or [{}])[0].get("expected_race_time")
            if data.get("evaluations")
            else None,
        },
        "uncertainty": data.get("uncertainty"),
        "confidence": data.get("confidence"),
        "evidence_tier": data.get("evidence_tier"),
        "explanation": {"reasoning": data.get("reasoning"), "components": data.get("components")},
        "provenance": data.get("provenance"),
        "constraints": data.get("constraints"),
        "raw": data,
    }


def evaluate_strategy_state_object(
    state: StrategyState, track_pit_loss: float = 22.0, seed: int | None = 42
) -> dict[str, Any]:
    return evaluate_strategy(state.model_dump(), track_pit_loss=track_pit_loss, seed=seed)
