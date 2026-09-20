from fastapi import APIRouter

from app.api.v1.endpoints import (
    health,
    metadata,
    metrics,
    races,
    replay,
    scenario,
    simulate,
    simulation,
    strategy,
)

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(metadata.router, prefix="/metadata", tags=["metadata"])
api_router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
api_router.include_router(races.router, prefix="/races", tags=["races"])
api_router.include_router(simulate.router, prefix="/simulate", tags=["simulation"])
api_router.include_router(strategy.router, prefix="/strategy", tags=["strategy"])
api_router.include_router(scenario.router, prefix="/scenario", tags=["scenario"])
api_router.include_router(replay.router, prefix="/replay", tags=["replay"])
api_router.include_router(simulation.router, prefix="/simulation", tags=["simulation"])
