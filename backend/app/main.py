from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from supabase import Client, ClientOptions, create_client

from app.config import Settings
from app.dependencies import get_classification_service, get_supabase
from app.errors import (
    ApiError,
    CorrelationIdMiddleware,
    RequestTimeoutMiddleware,
    api_error_handler,
    unexpected_error_handler,
)
from app.models.observability import MetricsSnapshot, ReadinessResponse
from app.observability import MetricsRegistry
from app.routes.chat import router as chat_router
from app.routes.classification import router as classification_router
from app.routes.patents import router as patents_router
from app.services.classification_service import ClassificationService, CpcIndexError
from app.services.gemini_client import GeminiFallbackClient

LOCAL_NETWORK_ORIGIN_REGEX = (
    r"^http://(?:localhost|127\.0\.0\.1|"
    r"10(?:\.\d{1,3}){3}|"
    r"192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})"
    r"(?::\d+)?$"
)

SupabaseFactory = Callable[[str, str], Client]
GeminiFactory = Callable[[str], GeminiFallbackClient]
ClassificationFactory = Callable[[GeminiFallbackClient], ClassificationService]


def _close_supabase(client: Client) -> None:
    """Close HTTP sessions that supabase-py created during the process lifetime."""
    postgrest = getattr(client, "_postgrest", None)
    if postgrest is not None:
        postgrest.aclose()
    auth = getattr(client, "auth", None)
    if auth is not None:
        auth.close()


def _check_supabase(client: Client) -> None:
    client.table("patentes").select("id").limit(1).execute()


def _check_cpc_index(service: ClassificationService) -> None:
    service.check_index()


def create_app(
    app_settings: Settings | None = None,
    *,
    supabase_factory: SupabaseFactory | None = None,
    gemini_factory: GeminiFactory | None = None,
    classification_factory: ClassificationFactory | None = None,
) -> FastAPI:
    settings = app_settings or Settings()
    metrics = MetricsRegistry()
    make_supabase = supabase_factory or (
        lambda url, key: create_client(
            url,
            key,
            options=ClientOptions(
                postgrest_client_timeout=settings.supabase_timeout_seconds,
            ),
        )
    )
    make_gemini = gemini_factory or (
        lambda key: GeminiFallbackClient(
            key,
            timeout_seconds=settings.gemini_timeout_seconds,
            metrics=metrics,
        )
    )
    make_classification = classification_factory or (
        lambda gemini: ClassificationService(gemini_client=gemini, metrics=metrics)
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        supabase = make_supabase(settings.supabase_url, settings.supabase_key)
        gemini = make_gemini(settings.gemini_api_key)
        application.state.supabase = supabase
        application.state.gemini = gemini
        application.state.classification_service = make_classification(gemini)
        try:
            yield
        finally:
            _close_supabase(supabase)

    application = FastAPI(
        title="Patentologos API",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.metrics = metrics

    application.add_exception_handler(ApiError, api_error_handler)
    application.add_exception_handler(Exception, unexpected_error_handler)
    application.add_middleware(CorrelationIdMiddleware, metrics=metrics)
    application.add_middleware(
        RequestTimeoutMiddleware,
        timeout_seconds=settings.request_timeout_seconds,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_origin_regex=(
            LOCAL_NETWORK_ORIGIN_REGEX
            if settings.allow_local_network_origins
            and settings.app_environment != "production"
            else None
        ),
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID"],
    )

    application.include_router(patents_router)
    application.include_router(chat_router)
    application.include_router(classification_router)

    @application.get("/")
    @application.get("/health/live")
    def liveness() -> dict[str, str]:
        return {"status": "ok", "service": "patentologos-api"}

    @application.get("/health/ready", response_model=ReadinessResponse)
    def readiness(
        supabase: Client = Depends(get_supabase),
        classification: ClassificationService = Depends(get_classification_service),
    ) -> JSONResponse:
        checks = {
            "configuration": "ok",
            "gemini": "configured",
        }
        try:
            _check_supabase(supabase)
            checks["supabase"] = "ok"
        except Exception:
            checks["supabase"] = "unavailable"
        try:
            _check_cpc_index(classification)
            checks["cpc_index"] = "ok"
        except (CpcIndexError, OSError, ValueError):
            checks["cpc_index"] = "unavailable"

        ready = "unavailable" not in checks.values()
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"status": "ready" if ready else "not_ready", "checks": checks},
        )

    @application.get("/metrics", response_model=MetricsSnapshot)
    def metrics_snapshot() -> MetricsSnapshot:
        return MetricsSnapshot.model_validate(metrics.snapshot())

    return application


app = create_app()
