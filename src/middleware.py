import logging
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        """Log requests with an ID, status, and duration."""

        request_id = uuid.uuid4().hex[:8]
        request.state.request_id = request_id
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            logger.error(
                f"Unhandled exception | Request ID: {request_id} | "
                f"Method: {request.method} | Path: {request.url.path}",
                exc_info=True
            )
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )

        duration_ms = (time.perf_counter() - start_time) * 1000

        status_code = response.status_code

        if status_code >= 500:
            log_level = logging.ERROR
        elif status_code >= 400:
            log_level = logging.WARNING
        else:
            log_level = logging.INFO

        logger.log(
            log_level,
            f"Request ID: {request_id} | "
            f"Method: {request.method} | "
            f"Path: {request.url.path} | "
            f"Status: {status_code} | "
            f"Duration: {duration_ms:.2f}ms"
        )

        response.headers["X-Request-ID"] = request_id

        return response