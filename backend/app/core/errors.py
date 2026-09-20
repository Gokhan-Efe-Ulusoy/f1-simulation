"""Phase 28 — Structured API error model."""

from __future__ import annotations

from enum import Enum

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorCode(str, Enum):  # noqa: UP042 - StrEnum needs 3.11, keep compat
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    RACE_NOT_FOUND = "RACE_NOT_FOUND"
    DATA_NOT_AVAILABLE = "DATA_NOT_AVAILABLE"
    DATA_PARTIAL = "DATA_PARTIAL"
    UNSUPPORTED_INTERVENTION = "UNSUPPORTED_INTERVENTION"
    SCIENTIFIC_NON_IDENTIFIABLE = "SCIENTIFIC_NON_IDENTIFIABLE"
    SIMULATION_LIMIT_EXCEEDED = "SIMULATION_LIMIT_EXCEEDED"
    INVALID_SEED = "INVALID_SEED"
    INVALID_LAP_RANGE = "INVALID_LAP_RANGE"
    INTERNAL_SIMULATION_ERROR = "INTERNAL_SIMULATION_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"


class APIError(BaseModel):
    code: str
    message: str
    details: dict | None = None


class APIErrorResponse(BaseModel):
    error: APIError


def error_response(
    code: ErrorCode | str, message: str, status_code: int = 400, details: dict | None = None
) -> JSONResponse:
    c = code.value if isinstance(code, ErrorCode) else str(code)
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": c, "message": message, "details": details or {}}},
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # type: ignore[no-untyped-def]  # noqa: E501
    return error_response(ErrorCode.VALIDATION_ERROR, str(exc), status_code=422)


def http_error(
    code: ErrorCode, message: str, status_code: int, details: dict | None = None
) -> JSONResponse:
    return error_response(code, message, status_code=status_code, details=details)
