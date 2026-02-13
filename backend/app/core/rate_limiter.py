"""Rate limiter using the pluggable cache backend.

Implements a sliding window rate limiter for API endpoints.
"""

from fastapi import HTTPException, status
from app.core.cache import get_cache


class RateLimiter:
    """Simple rate limiter using cache backend.

    Uses a fixed window approach: tracks request count per window.
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def check(self, key: str) -> dict:
        """Check rate limit for a key. Returns limit info.

        Raises HTTPException 429 if limit exceeded.
        """
        cache = get_cache()
        cache_key = f"ratelimit:{key}"

        count = cache.incr(cache_key)
        if count == 1:
            # First request in window, set expiration
            cache.expire(cache_key, self.window_seconds)

        remaining = max(0, self.max_requests - count)
        info = {
            "limit": self.max_requests,
            "remaining": remaining,
            "window": self.window_seconds,
        }

        if count > self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {self.max_requests} requests per {self.window_seconds}s.",
                headers={
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(self.window_seconds),
                },
            )

        return info


# Pre-configured rate limiters
llm_rate_limiter = RateLimiter(max_requests=30, window_seconds=60)  # 30 LLM calls/min
api_rate_limiter = RateLimiter(max_requests=120, window_seconds=60)  # 120 API calls/min
