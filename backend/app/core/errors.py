import uuid
from typing import Optional, Dict, Any
from fastapi import Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    """Application level exception that serializes to the standard error format."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        request_id: Optional[str] = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.request_id = request_id
        super().__init__(message)


def generate_request_id() -> str:
    return f"r-{uuid.uuid4().hex[:6]}"


def format_error_response(code: str, message: str, request_id: str) -> Dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    request_id = exc.request_id or getattr(request.state, "request_id", generate_request_id())
    return JSONResponse(
        status_code=exc.status_code,
        content=format_error_response(exc.code, exc.message, request_id),
    )


import logging

logger = logging.getLogger(__name__)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", generate_request_id())
    logger.exception(f"Unhandled server exception [request_id={request_id}]: {exc}")
    return JSONResponse(
        status_code=500,
        content=format_error_response(
            "INTERNAL_ERROR",
            "An internal server error occurred. Please contact system support.",
            request_id,
        ),
    )
