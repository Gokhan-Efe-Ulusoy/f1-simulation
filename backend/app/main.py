from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import ErrorCode, error_response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager."""
    # Startup: init DB
    try:
        from app.core.database import init_db

        init_db()
    except Exception:
        pass
    yield
    # Shutdown


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="F1 Simulation API",
        description="Formula 1 Simulation Platform — Phase 29 unified execution, persistent results, production API (deterministic, thin layer over existing engines). Scientific limitations: fuel NON_IDENTIFIABLE, tyre historical NON_IDENTIFIABLE, setup/strategy/weather/race_control PRIOR_ONLY, driver/circuit LIMITED.",  # noqa: E501
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Structured error handlers (never leak stack traces in production)
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, exc):  # type: ignore[no-untyped-def]
        return JSONResponse(
            status_code=422,
            content={"error": {"code": ErrorCode.VALIDATION_ERROR.value, "message": str(exc), "details": {}}},  # noqa: E501
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(request, exc):  # type: ignore[no-untyped-def]
        code = ErrorCode.VALIDATION_ERROR.value if exc.status_code == 422 else "HTTP_ERROR"
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": str(exc.detail), "details": {}}},
        )

    # Include API router
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
