"""Rate limiting middleware for API endpoints.

Uses user ID (authenticated) or client IP as the rate limit key.
Applies per-endpoint limits and adds X-RateLimit headers to responses.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.core.rate_limiter import RateLimiter

# Separate limiters for different endpoint types
_api_limiter = RateLimiter(max_requests=120, window_seconds=60)
_llm_limiter = RateLimiter(max_requests=30, window_seconds=60)
_auth_limiter = RateLimiter(max_requests=20, window_seconds=60)


def _get_client_key(request: Request) -> str:
    """Extract rate limit key: user ID from JWT or client IP."""
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
    # Fall back to IP
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
