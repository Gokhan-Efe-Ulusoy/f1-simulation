"""POST /strategy/evaluate."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.v1.schemas import StrategyEvaluateRequest, StrategyEvaluateResponse
from app.core.errors import ErrorCode, error_response
from app.services.strategy_service import evaluate_strategy

router = APIRouter()


@router.post(
    "/evaluate",
    response_model=StrategyEvaluateResponse,
    summary="Evaluate strategy decision",
    description="Uses existing DecisionEngine (Phase 19). Leakage-safe: rejects future_* fields. Returns recommended action, candidates, evaluations, explanation, provenance.",  # noqa: E501
)
async def strategy_evaluate_endpoint(req: StrategyEvaluateRequest) -> Any:
    try:
        result = evaluate_strategy(req.state, track_pit_loss=req.track_pit_loss, seed=req.seed)
    except ValueError as e:
        msg = str(e)
        if "leakage" in msg.lower():
            return error_response(ErrorCode.UNSUPPORTED_INTERVENTION, msg, status_code=400)  # type: ignore[return-value]  # noqa: E501
        return error_response(ErrorCode.INVALID_CONFIGURATION, msg, status_code=400)  # type: ignore[return-value]  # noqa: E501
    except Exception as e:
        return error_response(
            ErrorCode.INTERNAL_SIMULATION_ERROR, f"strategy evaluation failed: {e}", status_code=500
        )  # type: ignore[return-value]
    return result
