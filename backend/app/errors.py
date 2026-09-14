import asyncio
import logging
import time
import traceback
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from starlette.types import Message, Receive, Scope, Send

from app.observability import MetricsRegistry, log_event

logger = logging.getLogger(__name__)

CORRELATION_ID_HEADER = "X-Correlation-ID"
INTERNAL_ERROR_CODE = "INTERNAL_ERROR"
INTERNAL_ERROR_MESSAGE = "Ocurrió un error interno. Intenta de nuevo más tarde."


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message = message


class ExternalServiceTimeoutError(ApiError):
    def __init__(self, provider: str) -> None:
        super().__init__(
            504,
            "EXTERNAL_SERVICE_TIMEOUT",
            f"{provider} tardó demasiado en responder. Intenta nuevamente.",
        )


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, timeout_seconds: float) -> None:
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout_seconds,
            )
        except TimeoutError:
            correlation_id = _correlation_id(request)
            log_event(
                logger,
                logging.WARNING,
                "request_timeout",
                correlation_id=correlation_id,
                duration_ms=round(self.timeout_seconds * 1000, 2),
                status=504,
            )
            return _response(
                504,
                "REQUEST_TIMEOUT",
                "La solicitud excedió el tiempo máximo. Intenta nuevamente.",
                correlation_id,
            )


class CorrelationIdMiddleware:
    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        metrics: MetricsRegistry,
    ) -> None:
        self.app = app
        self.metrics = metrics

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = str(uuid4())
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        started_at = time.perf_counter()
        status_code = 500
        self.metrics.add_gauge("http_requests_in_flight", 1)

        async def send_with_correlation_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                header_name = CORRELATION_ID_HEADER.lower().encode("ascii")
                if not any(name == header_name for name, _ in headers):
                    headers.append(
                        (
                            header_name,
                            correlation_id.encode("ascii"),
                        )
                    )
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation_id)
        finally:
            duration = time.perf_counter() - started_at
            route = getattr(scope.get("route"), "path", "unmatched")
            method = scope.get("method", "UNKNOWN")
            status = str(status_code)
            self.metrics.add_gauge("http_requests_in_flight", -1)
            self.metrics.increment(
                "http_requests_total",
                method=method,
                route=route,
                status=status,
            )
            self.metrics.observe(
                "http_request_duration_seconds",
                duration,
                method=method,
                route=route,
            )
            log_event(
                logger,
                logging.INFO,
                "request_completed",
                correlation_id=correlation_id,
                duration_ms=round(duration * 1000, 2),
                method=method,
                route=route,
                status=status,
            )


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", str(uuid4()))


def _response(status_code: int, code: str, message: str, correlation_id: str):
    return JSONResponse(
        status_code=status_code,
        content={
            "detail": message,
            "code": code,
            "correlation_id": correlation_id,
        },
        headers={CORRELATION_ID_HEADER: correlation_id},
    )


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    correlation_id = _correlation_id(request)
    log_event(
        logger,
        logging.WARNING,
        "api_error",
        correlation_id=correlation_id,
        error_type=exc.code,
        status=exc.status_code,
    )
    return _response(exc.status_code, exc.code, exc.message, correlation_id)


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    correlation_id = _correlation_id(request)
    stack_trace = "".join(traceback.format_tb(exc.__traceback__))
    log_event(
        logger,
        logging.ERROR,
        "unhandled_error",
        correlation_id=correlation_id,
        error_type=type(exc).__name__,
        stack_trace=stack_trace,
        status=500,
    )
    return _response(
        500,
        INTERNAL_ERROR_CODE,
        INTERNAL_ERROR_MESSAGE,
        correlation_id,
    )
