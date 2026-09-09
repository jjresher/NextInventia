import logging
import traceback
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.types import Message, Receive, Scope, Send

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


class CorrelationIdMiddleware:
    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

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

        async def send_with_correlation_id(message: Message) -> None:
            if message["type"] == "http.response.start":
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

        await self.app(scope, receive, send_with_correlation_id)


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
    logger.warning(
        "Public API error correlation_id=%s code=%s status=%s",
        correlation_id,
        exc.code,
        exc.status_code,
    )
    return _response(exc.status_code, exc.code, exc.message, correlation_id)


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    correlation_id = _correlation_id(request)
    stack_trace = "".join(traceback.format_tb(exc.__traceback__))
    logger.error(
        "Unhandled API error correlation_id=%s error_type=%s stack_trace=%s",
        correlation_id,
        type(exc).__name__,
        stack_trace,
    )
    return _response(
        500,
        INTERNAL_ERROR_CODE,
        INTERNAL_ERROR_MESSAGE,
        correlation_id,
    )
