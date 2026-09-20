"""GET /replay/{race_id} and checkpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.core.errors import ErrorCode, error_response
from app.services.replay_service import replay_race

router = APIRouter()


@router.get(
    "/{race_id}",
    summary="Replay historical race",
    description="Phase 22 replay: baseline replay with checkpoints. Returns NOT_AVAILABLE via evidence tiers if data missing, never fabricates.",  # noqa: E501
)
async def replay_endpoint(
    race_id: str,
    seed: int | None = Query(default=42, ge=-2147483648, le=2147483647),
    simulations: int = Query(default=60, ge=1, le=5000),
    laps: int | None = Query(default=None, ge=1, le=200),
    checkpoint: str | None = Query(
        default=None,
        description="Optional checkpoint: pre_race, lap_1, lap_5, lap_10, finish or lap number",
    ),
) -> Any:
    if ".." in race_id or "/" in race_id or "\\" in race_id or len(race_id) > 100:
        return error_response(ErrorCode.VALIDATION_ERROR, "invalid race_id", status_code=422)  # type: ignore[return-value]  # noqa: E501
    if checkpoint and len(str(checkpoint)) > 50:
        return error_response(
            ErrorCode.VALIDATION_ERROR, "checkpoint value too long", status_code=422
        )  # type: ignore[return-value]
    try:
        result = replay_race(
            race_id=race_id, seed=seed, simulations=simulations, laps=laps, checkpoint=checkpoint
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            return error_response(ErrorCode.RACE_NOT_FOUND, msg, status_code=404)  # type: ignore[return-value]  # noqa: E501
        if "checkpoint" in msg.lower():
            return error_response(ErrorCode.INVALID_LAP_RANGE, msg, status_code=400)  # type: ignore[return-value]  # noqa: E501
        return error_response(ErrorCode.INVALID_CONFIGURATION, msg, status_code=400)  # type: ignore[return-value]  # noqa: E501
    except Exception as e:
        return error_response(
            ErrorCode.INTERNAL_SIMULATION_ERROR, f"replay failed: {e}", status_code=500
        )  # type: ignore[return-value]
    return result
