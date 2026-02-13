"""Pluggable cache backend: in-memory (dev) or Redis (prod).

Usage:
    cache = get_cache()
    await cache.set("key", "value", ttl=60)
    value = await cache.get("key")
    await cache.delete("key")
"""

import time
from abc import ABC, abstractmethod
from typing import Any, Optional


class CacheBackend(ABC):
    """Abstract cache interface."""

    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        ...

    @abstractmethod
    def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    def incr(self, key: str) -> int:
        """Increment a key's integer value. Creates with value 1 if missing."""
        ...

    @abstractmethod
    def expire(self, key: str, ttl: int) -> None:
        """Set expiration on a key."""
        ...


class InMemoryBackend(CacheBackend):
    """In-memory cache for development/testing. Not suitable for multi-process."""

    def __init__(self):
        self._store: dict[str, tuple[str, Optional[float]]] = {}

    def _is_expired(self, key: str) -> bool:
        if key not in self._store:
            return True
        _, expires_at = self._store[key]
        if expires_at is not None and time.time() > expires_at:
            del self._store[key]
            return True
        return False

    def get(self, key: str) -> Optional[str]:
        if self._is_expired(key):
            return None
        return self._store[key][0]

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        expires_at = time.time() + ttl if ttl else None
        self._store[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def exists(self, key: str) -> bool:
        return not self._is_expired(key)

    def incr(self, key: str) -> int:
        if self._is_expired(key):
            self._store[key] = ("1", self._store.get(key, (None, None))[1])
            return 1
        current = int(self._store[key][0])
        new_val = current + 1
        expires_at = self._store[key][1]
        self._store[key] = (str(new_val), expires_at)
        return new_val

    def expire(self, key: str, ttl: int) -> None:
        if key in self._store:
            value = self._store[key][0]
            self._store[key] = (value, time.time() + ttl)

    def clear(self) -> None:
        """Clear all keys (useful for testing)."""
        self._store.clear()


class RedisBackend(CacheBackend):
    """Redis cache backend for production."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        try:
            import redis
            self._client = redis.from_url(redis_url, decode_responses=True)
        except ImportError:
            raise RuntimeError("redis package required. Install with: pip install redis")

    def get(self, key: str) -> Optional[str]:
        return self._client.get(key)

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        if ttl:
            self._client.setex(key, ttl, value)
        else:
            self._client.set(key, value)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def exists(self, key: str) -> bool:
        return bool(self._client.exists(key))

    def incr(self, key: str) -> int:
        return self._client.incr(key)

    def expire(self, key: str, ttl: int) -> None:
        self._client.expire(key, ttl)


# Singleton cache instance
_cache: Optional[CacheBackend] = None


def get_cache() -> CacheBackend:
    """Get the global cache instance."""
    global _cache
    if _cache is None:
        from app.config import settings
        if settings.REDIS_URL:
            _cache = RedisBackend(settings.REDIS_URL)
        else:
            _cache = InMemoryBackend()
    return _cache


def set_cache(backend: CacheBackend) -> None:
    """Override the global cache (for testing)."""
    global _cache
    _cache = backend


def reset_cache() -> None:
    """Reset the global cache instance."""
    global _cache
    _cache = None
