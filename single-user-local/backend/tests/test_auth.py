"""Tests for Authentication System (V2 Phase 2.1).

Covers:
- Password hashing
- JWT token creation/validation
- User registration & login
- Token refresh
- Protected endpoints (/auth/me)
- Backward compatibility (AUTH_ENABLED=false)
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


# ==================== Password Hashing Tests ====================


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "securePassword123!"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_wrong_password(self):
        hashed = hash_password("correct_password")
        assert not verify_password("wrong_password", hashed)

    def test_different_hashes(self):
        """Each hash should be different (due to salting)."""
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2
        assert verify_password("same_password", h1)
        assert verify_password("same_password", h2)


# ==================== JWT Token Tests ====================


class TestJWTTokens:
    def test_create_and_decode_access_token(self):
        token = create_access_token("user-123")
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"

    def test_create_and_decode_refresh_token(self):
        token = create_refresh_token("user-456")
        payload = decode_token(token)
        assert payload["sub"] == "user-456"
        assert payload["type"] == "refresh"

    def test_expired_token(self):
        from datetime import timedelta
        token = create_access_token("user-789", expires_delta=timedelta(seconds=-1))
        from jose import JWTError
        with pytest.raises(JWTError):
            decode_token(token)

    def test_invalid_token(self):
        from jose import JWTError
        with pytest.raises(JWTError):
            decode_token("invalid.token.here")


# ==================== Registration Tests ====================


class TestRegistration:
    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    def test_register_success(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "securePass123!",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["username"] == "testuser"
        assert data["is_active"] is True
        assert data["is_admin"] is False
        assert "hashed_password" not in data
        assert "password" not in data

    def test_register_duplicate_email(self, client):
        client.post("/api/auth/register", json={
            "email": "dup@example.com",
            "username": "user1",
            "password": "password123!",
        })
        resp = client.post("/api/auth/register", json={
            "email": "dup@example.com",
            "username": "user2",
            "password": "password123!",
        })
        assert resp.status_code == 409
        assert "Email already registered" in resp.json()["detail"]

    def test_register_duplicate_username(self, client):
        client.post("/api/auth/register", json={
            "email": "a@example.com",
            "username": "samename",
            "password": "password123!",
        })
        resp = client.post("/api/auth/register", json={
            "email": "b@example.com",
            "username": "samename",
            "password": "password123!",
        })
        assert resp.status_code == 409
        assert "Username already taken" in resp.json()["detail"]

    def test_register_invalid_email(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "not-an-email",
            "username": "testuser",
            "password": "password123!",
        })
        assert resp.status_code == 422

    def test_register_short_password(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "short",
        })
        assert resp.status_code == 422

    def test_register_invalid_username(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "test@example.com",
            "username": "bad user name!",
            "password": "password123!",
        })
        assert resp.status_code == 422


# ==================== Login Tests ====================


class TestLogin:
    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    @pytest.fixture
    def registered_user(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "login@example.com",
            "username": "loginuser",
            "password": "mypassword123",
        })
        return resp.json()

    def test_login_with_username(self, client, registered_user):
        resp = client.post("/api/auth/login", json={
            "username": "loginuser",
            "password": "mypassword123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_with_email(self, client, registered_user):
        resp = client.post("/api/auth/login", json={
            "username": "login@example.com",
            "password": "mypassword123",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, client, registered_user):
        resp = client.post("/api/auth/login", json={
            "username": "loginuser",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401
        assert "Invalid credentials" in resp.json()["detail"]

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "nobody",
            "password": "password123",
        })
        assert resp.status_code == 401


# ==================== Token Refresh Tests ====================


class TestTokenRefresh:
    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    @pytest.fixture
    def tokens(self, client):
        client.post("/api/auth/register", json={
            "email": "refresh@example.com",
            "username": "refreshuser",
            "password": "password123!",
        })
        resp = client.post("/api/auth/login", json={
            "username": "refreshuser",
            "password": "password123!",
        })
        return resp.json()

    def test_refresh_success(self, client, tokens):
        resp = client.post("/api/auth/refresh", json={
            "refresh_token": tokens["refresh_token"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        # Verify the new access token is valid
        payload = decode_token(data["access_token"])
        assert payload["type"] == "access"

    def test_refresh_with_access_token_fails(self, client, tokens):
        """Using an access token for refresh should fail."""
        resp = client.post("/api/auth/refresh", json={
            "refresh_token": tokens["access_token"],
        })
        assert resp.status_code == 401

    def test_refresh_invalid_token(self, client):
        resp = client.post("/api/auth/refresh", json={
            "refresh_token": "invalid.token.value",
        })
        assert resp.status_code == 401


# ==================== Protected Endpoint Tests ====================


class TestProtectedEndpoints:
    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    @pytest.fixture
    def auth_headers(self, client):
        client.post("/api/auth/register", json={
            "email": "protected@example.com",
            "username": "protecteduser",
            "password": "password123!",
        })
        resp = client.post("/api/auth/login", json={
            "username": "protecteduser",
            "password": "password123!",
        })
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_get_me_with_auth_enabled(self, client, auth_headers, monkeypatch):
        monkeypatch.setattr(settings, "AUTH_ENABLED", True)
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "protecteduser"
        assert data["email"] == "protected@example.com"

    def test_get_me_without_token_auth_enabled(self, client, monkeypatch):
        monkeypatch.setattr(settings, "AUTH_ENABLED", True)
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_get_me_invalid_token_auth_enabled(self, client, monkeypatch):
        monkeypatch.setattr(settings, "AUTH_ENABLED", True)
        resp = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 401

    def test_update_me(self, client, auth_headers, monkeypatch):
        monkeypatch.setattr(settings, "AUTH_ENABLED", True)
        resp = client.put("/api/auth/me", json={
            "username": "newname",
        }, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["username"] == "newname"

    def test_update_me_duplicate_email(self, client, auth_headers, monkeypatch):
        monkeypatch.setattr(settings, "AUTH_ENABLED", True)
        # Register another user
        client.post("/api/auth/register", json={
            "email": "other@example.com",
            "username": "otheruser",
            "password": "password123!",
        })
        # Try to take their email
        resp = client.put("/api/auth/me", json={
            "email": "other@example.com",
        }, headers=auth_headers)
        assert resp.status_code == 409


# ==================== Backward Compatibility Tests ====================


class TestBackwardCompatibility:
    """Verify AUTH_ENABLED=false doesn't break existing V1 endpoints."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    def test_v1_endpoints_work_without_auth(self, client, monkeypatch):
        """With AUTH_ENABLED=false, all V1 endpoints should work as before."""
        monkeypatch.setattr(settings, "AUTH_ENABLED", False)

        # Teams CRUD
        team = client.post("/api/teams/", json={"name": "Test Team"}).json()
        assert team["name"] == "Test Team"

        teams = client.get("/api/teams/").json()
        assert len(teams) >= 1

        # Health check
        assert client.get("/health").status_code == 200

    def test_register_works_regardless_of_auth_setting(self, client, monkeypatch):
        """Registration should work even when AUTH_ENABLED=false."""
        monkeypatch.setattr(settings, "AUTH_ENABLED", False)
        resp = client.post("/api/auth/register", json={
            "email": "noauth@example.com",
            "username": "noauthuser",
            "password": "password123!",
        })
        assert resp.status_code == 201

    def test_login_works_regardless_of_auth_setting(self, client, monkeypatch):
        """Login should work even when AUTH_ENABLED=false."""
        monkeypatch.setattr(settings, "AUTH_ENABLED", False)
        client.post("/api/auth/register", json={
            "email": "noauth2@example.com",
            "username": "noauth2",
            "password": "password123!",
        })
        resp = client.post("/api/auth/login", json={
            "username": "noauth2",
            "password": "password123!",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()
