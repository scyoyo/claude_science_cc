"""Rate limiting middleware for API endpoints.

Uses user ID (authenticated) or client IP as the rate limit key.
Applies per-endpoint limits and adds X-RateLimit headers to responses.
Limits are configurable via settings (RATE_LIMIT_*).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.core.rate_limiter import RateLimiter
from app.config import settings

# Limiters use config (env: RATE_LIMIT_API_MAX_REQUESTS, etc.)
_api_limiter = RateLimiter(
    max_requests=settings.RATE_LIMIT_API_MAX_REQUESTS,
    window_seconds=settings.RATE_LIMIT_API_WINDOW_SECONDS,
)
_llm_limiter = RateLimiter(max_requests=settings.RATE_LIMIT_LLM_MAX_REQUESTS, window_seconds=60)
_auth_limiter = RateLimiter(max_requests=settings.RATE_LIMIT_AUTH_MAX_REQUESTS, window_seconds=60)


def _get_client_key(request: Request) -> str:
    """Extract rate limit key: user ID from JWT or real client IP.

    On Railway/proxy setups, request.client.host is always 127.0.0.1.
    We use X-Forwarded-For to get the real client IP so each user gets
    their own rate limit bucket instead of sharing one.
    """
    # Check for Authorization header to get user identity
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            from app.core.auth import decode_token
            payload = decode_token(token)
            user_id = payload.get("sub")
            if user_id:
                return f"user:{user_id}"
        except Exception:
            pass
    # Use X-Forwarded-For for real client IP behind proxy
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # X-Forwarded-For: client, proxy1, proxy2 — take the first (client) IP
        ip = forwarded.split(",")[0].strip()
        return f"ip:{ip}"
    # Fall back to direct connection IP
    client = request.client
    ip = client.host if client else "unknown"
    return f"ip:{ip}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Skip non-API paths and health checks
        if not path.startswith("/api/") or path == "/health":
            return await call_next(request)

        key = _get_client_key(request)

        try:
            # Apply stricter limits for auth endpoints (brute force protection)
            if path.startswith("/api/auth/login") or path.startswith("/api/auth/register"):
                info = _auth_limiter.check(f"{key}:auth")
            # Stricter limit for LLM chat (expensive)
            elif path.startswith("/api/llm/chat"):
                info = _llm_limiter.check(f"{key}:llm")
            else:
                info = _api_limiter.check(key)
        except Exception as e:
            # Rate limit exceeded — HTTPException from RateLimiter
            from fastapi import HTTPException
            if isinstance(e, HTTPException) and e.status_code == 429:
                return JSONResponse(
                    status_code=429,
                    content={"detail": e.detail},
                    headers=e.headers or {},
                )
            raise

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])

        return response
