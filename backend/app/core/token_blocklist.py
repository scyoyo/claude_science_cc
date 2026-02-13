"""JWT token blocklist using the pluggable cache backend.

Used to invalidate refresh tokens (e.g., on logout or password change).
"""

from app.core.cache import get_cache


def block_token(token_jti: str, ttl: int = 604800) -> None:
    """Add a token to the blocklist.

    Args:
        token_jti: The token's unique identifier (user_id or token hash).
        ttl: How long to keep in blocklist (default: 7 days = refresh token lifetime).
    """
    cache = get_cache()
    cache.set(f"blocked_token:{token_jti}", "1", ttl=ttl)


def is_token_blocked(token_jti: str) -> bool:
    """Check if a token is blocked."""
    cache = get_cache()
    return cache.exists(f"blocked_token:{token_jti}")
