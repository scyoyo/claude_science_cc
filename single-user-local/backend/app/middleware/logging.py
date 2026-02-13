"""Structured request logging middleware.

Logs each request with method, path, status code, duration, and client info
in JSON format for easy parsing by log aggregation tools.
"""

import time
import logging
import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.access")


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.monotonic()

        # Process request
        response = await call_next(request)

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        # Extract client info
        client = request.client
        client_ip = client.host if client else "unknown"

        # Extract user ID from auth header if present
        user_id = None
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            try:
                from app.core.auth import decode_token
                payload = decode_token(auth[7:])
                user_id = payload.get("sub")
            except Exception:
                pass

        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
            "client_ip": client_ip,
        }

        if user_id:
            log_data["user_id"] = user_id

        if request.url.query:
            log_data["query"] = str(request.url.query)

        # Log level based on status code
        if response.status_code >= 500:
            logger.error(json.dumps(log_data))
        elif response.status_code >= 400:
            logger.warning(json.dumps(log_data))
        else:
            logger.info(json.dumps(log_data))

        # Add timing header
        response.headers["X-Response-Time"] = f"{duration_ms}ms"

        return response
