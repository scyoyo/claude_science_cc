"""Tests for LLM Client (Step 1.4).

Covers:
- Encryption: encrypt/decrypt API keys
- LLM providers: OpenAI, Anthropic, DeepSeek (mocked HTTP)
- Provider factory: create_provider, detect_provider
- Retry logic and error handling
- API key management endpoints
- LLM chat endpoint (mocked)
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from app.main import app
from app.core.encryption import encrypt_api_key, decrypt_api_key
from app.core.llm_client import (
    OpenAIProvider,
    AnthropicProvider,
    DeepSeekProvider,
    create_provider,
    detect_provider,
    LLMError,
    LLMAuthError,
    LLMRateLimitError,
    LLMProviderError,
    LLMResponse,
)
from app.schemas.onboarding import ChatMessage


# ==================== Encryption Tests ====================


class TestEncryption:
    """Tests for API key encryption/decryption."""

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypt then decrypt should return original."""
        secret = "my-secret-key"
        original = "sk-abc123xyz"
        encrypted = encrypt_api_key(original, secret)
        assert encrypted != original
        decrypted = decrypt_api_key(encrypted, secret)
        assert decrypted == original

    def test_different_secrets_different_output(self):
        """Different secrets should produce different encrypted values."""
        api_key = "sk-test123"
        e1 = encrypt_api_key(api_key, "secret1")
        e2 = encrypt_api_key(api_key, "secret2")
        assert e1 != e2

    def test_wrong_secret_fails(self):
        """Decrypting with wrong secret should raise an error."""
        encrypted = encrypt_api_key("sk-test", "correct-secret")
        with pytest.raises(Exception):
            decrypt_api_key(encrypted, "wrong-secret")


# ==================== Provider Factory Tests ====================


class TestProviderFactory:
    """Tests for provider detection and factory."""

    def test_detect_openai_gpt4(self):
        assert detect_provider("gpt-4") == "openai"

    def test_detect_openai_gpt35(self):
        assert detect_provider("gpt-3.5-turbo") == "openai"

    def test_detect_openai_o1(self):
        assert detect_provider("o1") == "openai"

    def test_detect_anthropic_claude(self):
        assert detect_provider("claude-3-opus-20240229") == "anthropic"

    def test_detect_deepseek(self):
        assert detect_provider("deepseek-chat") == "deepseek"

    def test_detect_unknown_raises(self):
        with pytest.raises(LLMError, match="Cannot detect provider"):
            detect_provider("unknown-model-123")

    def test_create_openai_provider(self):
        p = create_provider("openai", "sk-test")
        assert isinstance(p, OpenAIProvider)
        assert p.provider_name == "openai"

    def test_create_anthropic_provider(self):
        p = create_provider("anthropic", "sk-test")
        assert isinstance(p, AnthropicProvider)
        assert p.provider_name == "anthropic"

    def test_create_deepseek_provider(self):
        p = create_provider("deepseek", "sk-test")
        assert isinstance(p, DeepSeekProvider)
        assert p.provider_name == "deepseek"

    def test_create_unknown_provider_raises(self):
        with pytest.raises(LLMError, match="Unknown provider"):
            create_provider("unknown", "sk-test")


# ==================== Provider Request Building Tests ====================


class TestOpenAIProvider:
    """Tests for OpenAI provider request/response handling."""

    def setup_method(self):
        self.provider = OpenAIProvider(api_key="sk-test-key", max_retries=1, retry_delay=0)

    def test_build_request(self):
        messages = [ChatMessage(role="user", content="Hello")]
        url, headers, body = self.provider._build_request(messages, "gpt-4", {"temperature": 0.7})
        assert "openai.com" in url
        assert headers["Authorization"] == "Bearer sk-test-key"
        assert body["model"] == "gpt-4"
        assert body["messages"] == [{"role": "user", "content": "Hello"}]
        assert body["temperature"] == 0.7

    def test_parse_response(self):
        raw = {
            "choices": [{"message": {"content": "Hi there!"}}],
            "model": "gpt-4",
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        }
        result = self.provider._parse_response(raw, "gpt-4")
        assert result.content == "Hi there!"
        assert result.model == "gpt-4"
        assert result.provider == "openai"

    @patch("app.core.llm_client.httpx.Client")
    def test_chat_success(self, mock_client_cls):
        """Test successful chat request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}],
            "model": "gpt-4",
            "usage": {},
        }
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = self.provider.chat(
            [ChatMessage(role="user", content="Hello")],
            "gpt-4",
        )
        assert result.content == "Test response"
        assert result.provider == "openai"

    @patch("app.core.llm_client.httpx.Client")
    def test_auth_error_no_retry(self, mock_client_cls):
        """Auth errors should not be retried."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid API key"
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(LLMAuthError):
            self.provider.chat([ChatMessage(role="user", content="Hi")], "gpt-4")
        # Should only be called once (no retry)
        assert mock_client.post.call_count == 1

    @patch("app.core.llm_client.httpx.Client")
    def test_rate_limit_retries(self, mock_client_cls):
        """Rate limit errors should be retried."""
        provider = OpenAIProvider(api_key="sk-test", max_retries=3, retry_delay=0)
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limited"
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(LLMRateLimitError):
            provider.chat([ChatMessage(role="user", content="Hi")], "gpt-4")
        # Should retry max_retries times
        assert mock_client.post.call_count == 3

    @patch("app.core.llm_client.httpx.Client")
    def test_server_error_retries(self, mock_client_cls):
        """Server errors should be retried."""
        provider = OpenAIProvider(api_key="sk-test", max_retries=2, retry_delay=0)
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal error"
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(LLMProviderError):
            provider.chat([ChatMessage(role="user", content="Hi")], "gpt-4")
        assert mock_client.post.call_count == 2


class TestAnthropicProvider:
    """Tests for Anthropic provider."""

    def setup_method(self):
        self.provider = AnthropicProvider(api_key="sk-ant-test", max_retries=1, retry_delay=0)

    def test_build_request_with_system(self):
        messages = [
            ChatMessage(role="system", content="You are helpful"),
            ChatMessage(role="user", content="Hello"),
        ]
        url, headers, body = self.provider._build_request(messages, "claude-3-opus-20240229", {})
        assert "anthropic.com" in url
        assert headers["x-api-key"] == "sk-ant-test"
        assert body["system"] == "You are helpful"
        assert body["messages"] == [{"role": "user", "content": "Hello"}]
        assert body["max_tokens"] == 4096  # default

    def test_build_request_custom_max_tokens(self):
        messages = [ChatMessage(role="user", content="Hi")]
        _, _, body = self.provider._build_request(
            messages, "claude-3-opus-20240229", {"max_tokens": 1000}
        )
        assert body["max_tokens"] == 1000

    def test_parse_response(self):
        raw = {
            "content": [{"type": "text", "text": "Hello from Claude!"}],
            "model": "claude-3-opus-20240229",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
        result = self.provider._parse_response(raw, "claude-3-opus-20240229")
        assert result.content == "Hello from Claude!"
        assert result.provider == "anthropic"


class TestDeepSeekProvider:
    """Tests for DeepSeek provider."""

    def setup_method(self):
        self.provider = DeepSeekProvider(api_key="sk-ds-test", max_retries=1, retry_delay=0)

    def test_build_request(self):
        messages = [ChatMessage(role="user", content="Hello")]
        url, headers, body = self.provider._build_request(messages, "deepseek-chat", {})
        assert "deepseek.com" in url
        assert headers["Authorization"] == "Bearer sk-ds-test"

    def test_parse_response(self):
        raw = {
            "choices": [{"message": {"content": "DeepSeek reply"}}],
            "model": "deepseek-chat",
            "usage": {},
        }
        result = self.provider._parse_response(raw, "deepseek-chat")
        assert result.content == "DeepSeek reply"
        assert result.provider == "deepseek"


# ==================== API Key Management API Tests ====================


class TestAPIKeyManagementAPI:
    """Tests for the API key management endpoints."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    def test_create_api_key(self, client):
        """Create a new API key."""
        response = client.post("/api/llm/api-keys", json={
            "provider": "openai",
            "api_key": "sk-test-abcdef1234",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "openai"
        assert data["is_active"] is True
        assert data["key_preview"] == "...1234"

    def test_list_api_keys(self, client):
        """List stored API keys."""
        # Create one first
        client.post("/api/llm/api-keys", json={
            "provider": "openai",
            "api_key": "sk-test1234",
        })
        response = client.get("/api/llm/api-keys")
        assert response.status_code == 200
        keys = response.json()
        assert len(keys) == 1
        assert keys[0]["provider"] == "openai"

    def test_duplicate_provider_rejected(self, client):
        """Cannot create two active keys for the same provider."""
        client.post("/api/llm/api-keys", json={
            "provider": "openai",
            "api_key": "sk-first",
        })
        response = client.post("/api/llm/api-keys", json={
            "provider": "openai",
            "api_key": "sk-second",
        })
        assert response.status_code == 409

    def test_update_api_key(self, client):
        """Update an API key."""
        create_resp = client.post("/api/llm/api-keys", json={
            "provider": "anthropic",
            "api_key": "sk-ant-old-key1",
        })
        key_id = create_resp.json()["id"]

        update_resp = client.put(f"/api/llm/api-keys/{key_id}", json={
            "api_key": "sk-ant-new-key2",
        })
        assert update_resp.status_code == 200
        assert update_resp.json()["key_preview"] == "...key2"

    def test_deactivate_api_key(self, client):
        """Deactivate an API key."""
        create_resp = client.post("/api/llm/api-keys", json={
            "provider": "deepseek",
            "api_key": "sk-ds-test1234",
        })
        key_id = create_resp.json()["id"]

        update_resp = client.put(f"/api/llm/api-keys/{key_id}", json={
            "is_active": False,
        })
        assert update_resp.status_code == 200
        assert update_resp.json()["is_active"] is False

    def test_delete_api_key(self, client):
        """Delete an API key."""
        create_resp = client.post("/api/llm/api-keys", json={
            "provider": "openai",
            "api_key": "sk-to-delete1",
        })
        key_id = create_resp.json()["id"]

        delete_resp = client.delete(f"/api/llm/api-keys/{key_id}")
        assert delete_resp.status_code == 204

        # Verify it's gone
        list_resp = client.get("/api/llm/api-keys")
        assert len(list_resp.json()) == 0

    def test_delete_nonexistent_key(self, client):
        """Deleting a non-existent key returns 404."""
        response = client.delete("/api/llm/api-keys/nonexistent-id")
        assert response.status_code == 404

    def test_update_nonexistent_key(self, client):
        """Updating a non-existent key returns 404."""
        response = client.put("/api/llm/api-keys/nonexistent-id", json={
            "is_active": False,
        })
        assert response.status_code == 404


class TestLLMProvidersEndpoint:
    """Tests for the providers listing endpoint."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    def test_list_providers(self, client):
        """List available LLM providers."""
        response = client.get("/api/llm/providers")
        assert response.status_code == 200
        providers = response.json()["providers"]
        assert "openai" in providers
        assert "anthropic" in providers
        assert "deepseek" in providers


class TestLLMChatEndpoint:
    """Tests for the LLM chat endpoint."""

    @pytest.fixture
    def client(self):
        with TestClient(app) as c:
            yield c

    def test_chat_no_api_key(self, client):
        """Chat fails without stored API key."""
        response = client.post("/api/llm/chat", json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
        })
        assert response.status_code == 400
        assert "No active API key" in response.json()["detail"]

    @patch("app.core.llm_client.httpx.Client")
    def test_chat_with_stored_key(self, mock_client_cls, client):
        """Chat succeeds with a stored API key and mocked HTTP."""
        # Store an API key
        client.post("/api/llm/api-keys", json={
            "provider": "openai",
            "api_key": "sk-real-key-test",
        })

        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Mocked response"}}],
            "model": "gpt-4",
            "usage": {"prompt_tokens": 5, "completion_tokens": 10},
        }
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client_cls.return_value = mock_client

        response = client.post("/api/llm/chat", json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Mocked response"
        assert data["provider"] == "openai"
