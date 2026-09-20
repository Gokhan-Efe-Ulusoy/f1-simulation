from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str
    simulation_model_version: str


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    from app.core.config import simulation_config

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        simulation_model_version=simulation_config.model_version,
    )
