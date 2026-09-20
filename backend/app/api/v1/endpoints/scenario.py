"""POST /scenario/compare."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.v1.schemas import ScenarioCompareRequest, ScenarioCompareResponse
from app.core.errors import ErrorCode, error_response
from app.services.scenario_service import compare_scenario

router = APIRouter()


@router.post(
    "/compare",
    response_model=ScenarioCompareResponse,
    summary="Compare baseline vs counterfactual scenario",
    description="Uses existing registry/validation/compiler/engine (Phase 21/22). Allowlist-enforced, leakage blocklist enforced. Returns trace, comparison, attribution, provenance.",  # noqa: E501
)
async def scenario_compare_endpoint(req: ScenarioCompareRequest) -> Any:
    try:
        result = compare_scenario(
            race_id=req.race_id,
            interventions=req.interventions,
            seed=req.seed,
            simulations=req.simulations,
            laps=req.laps,
            experiment_id=req.experiment_id,
            question=req.question,
        )
    except ValueError as e:
        msg = str(e)
        low = msg.lower()
        if any(
            s in low
            for s in (
                "leakage",
                "rejected",
                "unknown intervention",
                "unknown parameter",
                "unknown driver",
                "unknown constructor",
                "unknown target",
                "out of model bounds",
                "conflicting",
                "must be",
            )
        ):
            return error_response(ErrorCode.UNSUPPORTED_INTERVENTION, msg, status_code=400)  # type: ignore[return-value]  # noqa: E501
        if "race" in low and "not found" in low:
            return error_response(ErrorCode.RACE_NOT_FOUND, msg, status_code=404)  # type: ignore[return-value]  # noqa: E501
        return error_response(ErrorCode.INVALID_CONFIGURATION, msg, status_code=400)  # type: ignore[return-value]  # noqa: E501
    except RuntimeError as e:
        return error_response(ErrorCode.INTERNAL_SIMULATION_ERROR, str(e), status_code=500)  # type: ignore[return-value]  # noqa: E501
    except Exception as e:
        return error_response(
            ErrorCode.INTERNAL_SIMULATION_ERROR, f"scenario failed: {e}", status_code=500
        )  # type: ignore[return-value]
    return result
