"""Request logging and timing middleware."""

import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("riva.backend.access")


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Logs incoming HTTP requests and tracks execution duration."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Don't spam logs for frequent polling or static assets unless debug
        if not request.url.path.startswith(("/static", "/favicon.ico")):
            logger.info(
                "%s %s %d - %.2fms",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )

        response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"
        return response
