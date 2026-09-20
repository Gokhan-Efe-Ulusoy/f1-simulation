"""GET /races and GET /races/{race_id}."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.core.errors import ErrorCode, error_response
from app.services.race_service import get_race, list_races

router = APIRouter()


@router.get(
    "",
    summary="List races",
    description="List canonical races with filters season/circuit/driver/constructor. Uses cached metadata, not full dataset per request.",  # noqa: E501
)
async def list_races_endpoint(
    season: str | None = Query(default=None, description="Filter by season_id e.g. 2024"),
    circuit: str | None = Query(default=None, description="Filter by circuit_id"),
    driver: str | None = Query(default=None, description="Filter by driver_id"),
    constructor: str | None = Query(default=None, description="Filter by constructor_id"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    # input size guard
    for v in [season, circuit, driver, constructor]:
        if v and len(v) > 100:
            return error_response(
                ErrorCode.VALIDATION_ERROR, "filter value too long", status_code=422
            )  # type: ignore[return-value]
    races, total = list_races(
        season=season,
        circuit=circuit,
        driver=driver,
        constructor=constructor,
        limit=limit,
        offset=offset,
    )
    return {"races": races, "total": total, "limit": limit, "offset": offset}


@router.get(
    "/{race_id}",
    summary="Get race detail",
    description="Get single race metadata + availability. Returns 404 if not found.",
)
async def get_race_endpoint(race_id: str) -> dict[str, Any]:
    if ".." in race_id or "/" in race_id or "\\" in race_id or len(race_id) > 100:
        return error_response(ErrorCode.VALIDATION_ERROR, "invalid race_id", status_code=422)  # type: ignore[return-value]  # noqa: E501
    rec = get_race(race_id)
    if not rec:
        return error_response(
            ErrorCode.RACE_NOT_FOUND,
            f"race {race_id!r} not found",
            status_code=404,
            details={"race_id": race_id},
        )  # type: ignore[return-value]
    return rec
