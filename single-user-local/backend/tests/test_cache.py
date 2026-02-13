"""Tests for Cache, Rate Limiter, and Token Blocklist (V2 Phase 2.3).

Tests use InMemoryBackend (no Redis required).
"""

import time
import pytest
from fastapi import HTTPException
from app.core.cache import InMemoryBackend, get_cache, set_cache, reset_cache
from app.core.rate_limiter import RateLimiter
from app.core.token_blocklist import block_token, is_token_blocked


# ==================== InMemoryBackend Tests ====================


class TestInMemoryBackend:
    def setup_method(self):
        self.cache = InMemoryBackend()

    def test_set_and_get(self):
        self.cache.set("key1", "value1")
        assert self.cache.get("key1") == "value1"

    def test_get_missing_key(self):
        assert self.cache.get("nonexistent") is None

    def test_delete(self):
        self.cache.set("key1", "value1")
        self.cache.delete("key1")
        assert self.cache.get("key1") is None

    def test_exists(self):
        assert not self.cache.exists("key1")
        self.cache.set("key1", "value1")
        assert self.cache.exists("key1")

    def test_ttl_expiration(self):
        self.cache.set("key1", "value1", ttl=1)
        assert self.cache.get("key1") == "value1"
        time.sleep(1.1)
        assert self.cache.get("key1") is None

    def test_incr_new_key(self):
        result = self.cache.incr("counter")
        assert result == 1

    def test_incr_existing_key(self):
        self.cache.set("counter", "5")
        result = self.cache.incr("counter")
        assert result == 6

    def test_expire(self):
        self.cache.set("key1", "value1")
        self.cache.expire("key1", 1)
        assert self.cache.get("key1") == "value1"
        time.sleep(1.1)
        assert self.cache.get("key1") is None

    def test_clear(self):
        self.cache.set("a", "1")
        self.cache.set("b", "2")
        self.cache.clear()
        assert self.cache.get("a") is None
        assert self.cache.get("b") is None

    def test_overwrite(self):
        self.cache.set("key1", "old")
        self.cache.set("key1", "new")
        assert self.cache.get("key1") == "new"


# ==================== Rate Limiter Tests ====================


class TestRateLimiter:
    def setup_method(self):
        self.backend = InMemoryBackend()
        set_cache(self.backend)

    def teardown_method(self):
        reset_cache()

    def test_within_limit(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for i in range(5):
            info = limiter.check("user:1")
            assert info["remaining"] == 5 - (i + 1)

    def test_exceed_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.check("user:2")

        with pytest.raises(HTTPException) as exc_info:
            limiter.check("user:2")
        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail

    def test_different_keys_independent(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.check("user:a")
        limiter.check("user:a")

        # user:b should still have quota
        info = limiter.check("user:b")
        assert info["remaining"] == 1

    def test_rate_limit_info(self):
        limiter = RateLimiter(max_requests=10, window_seconds=30)
        info = limiter.check("user:3")
        assert info["limit"] == 10
        assert info["remaining"] == 9
        assert info["window"] == 30


# ==================== Token Blocklist Tests ====================


class TestTokenBlocklist:
    def setup_method(self):
        self.backend = InMemoryBackend()
        set_cache(self.backend)

    def teardown_method(self):
        reset_cache()

    def test_block_and_check(self):
        assert not is_token_blocked("token-123")
        block_token("token-123")
        assert is_token_blocked("token-123")

    def test_unblocked_token(self):
        assert not is_token_blocked("never-blocked")

    def test_block_with_ttl(self):
        block_token("token-456", ttl=1)
        assert is_token_blocked("token-456")
        time.sleep(1.1)
        assert not is_token_blocked("token-456")


# ==================== Cache Singleton Tests ====================


class TestCacheSingleton:
    def teardown_method(self):
        reset_cache()

    def test_get_cache_returns_in_memory_by_default(self):
        reset_cache()
        cache = get_cache()
        assert isinstance(cache, InMemoryBackend)

    def test_set_cache_override(self):
        custom = InMemoryBackend()
        set_cache(custom)
        assert get_cache() is custom
