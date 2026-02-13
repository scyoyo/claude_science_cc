"""Tests for rate limiting middleware (V3 Phase 3.3).

Verifies:
- Rate limit headers present on API responses
- 429 returned when limit exceeded
- Non-API paths bypass rate limiting
- Different limits for auth/llm/general endpoints
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.cache import InMemoryBackend, set_cache, reset_cache


@pytest.fixture(autouse=True)
def fresh_cache():
    """Use fresh in-memory cache per test to avoid rate limit carry-over."""
    backend = InMemoryBackend()
    set_cache(backend)
    yield
    reset_cache()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestRateLimitHeaders:
    def test_api_response_has_rate_limit_headers(self, client):
        resp = client.get("/api/teams/")
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == "120"

    def test_health_endpoint_no_rate_limit(self, client):
        resp = client.get("/health")
        assert "X-RateLimit-Limit" not in resp.headers

    def test_root_endpoint_no_rate_limit(self, client):
        resp = client.get("/")
        assert "X-RateLimit-Limit" not in resp.headers


class TestRateLimitEnforcement:
    def test_api_rate_limit_enforcement(self, client):
        """Exceed 120 requests/min and get 429."""
        for i in range(120):
            resp = client.get("/api/teams/")
            assert resp.status_code == 200

        resp = client.get("/api/teams/")
        assert resp.status_code == 429
        assert "Rate limit exceeded" in resp.json()["detail"]

    def test_auth_rate_limit_stricter(self, client):
        """Auth endpoints limited to 20 requests/min."""
        for i in range(20):
            resp = client.post(
                "/api/auth/login",
                json={"username": "test", "password": "test1234"},
            )
            # Will get 401 (invalid creds) but should not be rate limited yet
            assert resp.status_code in (401, 200)

        resp = client.post(
            "/api/auth/login",
            json={"username": "test", "password": "test1234"},
        )
        assert resp.status_code == 429

    def test_remaining_count_decreases(self, client):
        r1 = client.get("/api/teams/")
        r2 = client.get("/api/teams/")
        remaining1 = int(r1.headers["X-RateLimit-Remaining"])
        remaining2 = int(r2.headers["X-RateLimit-Remaining"])
        assert remaining2 == remaining1 - 1
