"""GET /metadata — dataset, model versions, evidence tiers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.schemas import MetadataResponse
from app.services.metadata_service import get_metadata

router = APIRouter()


@router.get(
    "",
    response_model=MetadataResponse,
    summary="Get platform metadata and evidence tiers",
    description="Returns dataset version, all model versions, and scientific evidence tiers (NON_IDENTIFIABLE etc).",  # noqa: E501
)
async def get_metadata_endpoint() -> dict:
    return get_metadata()  # type: ignore[return-value]
