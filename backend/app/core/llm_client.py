"""
LLM Client: Unified interface for multiple LLM providers.

Supports OpenAI, Anthropic (Claude), and DeepSeek with:
- Provider factory pattern
- Retry logic with exponential backoff
- Standardized request/response format
- Error handling and rate limit awareness
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.schemas.onboarding import ChatMessage


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    content: str
    model: str
    provider: str
    usage: Dict = field(default_factory=dict)  # token counts
    raw_response: Optional[Dict] = None


class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass


class LLMAuthError(LLMError):
    """Invalid or missing API key."""
    pass


class LLMRateLimitError(LLMError):
    """Rate limit exceeded (temporary)."""
    pass


class LLMQuotaError(LLMError):
    """API quota/billing exhausted (not temporary — needs user action)."""
    pass


class LLMProviderError(LLMError):
    """Provider-side error (5xx)."""
    pass


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(
        self,
        api_key: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 60.0,
    ):
        self.api_key = api_key
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'openai', 'anthropic')."""
        ...

    @abstractmethod
    def _build_request(
        self,
        messages: List[ChatMessage],
        model: str,
        params: Dict,
    ) -> tuple[str, Dict, Dict]:
        """Build the HTTP request. Returns (url, headers, body)."""
        ...

    @abstractmethod
    def _parse_response(self, data: Dict, model: str) -> LLMResponse:
        """Parse provider-specific response into LLMResponse."""
        ...

    def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        params: Optional[Dict] = None,
    ) -> LLMResponse:
        """Send a chat completion request with retry logic.

        Args:
            messages: Conversation history.
            model: Model identifier (e.g., 'gpt-4', 'claude-3-opus-20240229').
            params: Optional model parameters (temperature, max_tokens, etc.).

        Returns:
            LLMResponse with the model's reply.
        """
        params = params or {}
        url, headers, body = self._build_request(messages, model, params)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                return self._send_request(url, headers, body, model)
            except LLMRateLimitError as e:
                last_error = e
                delay = self.retry_delay * (2 ** attempt)
                time.sleep(delay)
            except LLMProviderError as e:
                last_error = e
                delay = self.retry_delay * (2 ** attempt)
                time.sleep(delay)
            except LLMAuthError:
                raise  # Don't retry auth errors
            except LLMQuotaError:
                raise  # Don't retry quota errors — needs user action

        raise last_error  # type: ignore

    def _send_request(
        self,
        url: str,
        headers: Dict,
        body: Dict,
        model: str,
    ) -> LLMResponse:
        """Execute the HTTP request and handle status codes."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=headers, json=body)

        if response.status_code == 401 or response.status_code == 403:
            raise LLMAuthError(f"Authentication failed: {response.text}")
        elif response.status_code == 429:
            text = response.text
            if "insufficient_quota" in text or "billing" in text.lower():
                raise LLMQuotaError(f"API quota exhausted: {text}")
            raise LLMRateLimitError(f"Rate limit exceeded: {text}")
        elif response.status_code >= 500:
            raise LLMProviderError(f"Provider error ({response.status_code}): {response.text}")
        elif response.status_code != 200:
            raise LLMError(f"Request failed ({response.status_code}): {response.text}")

        return self._parse_response(response.json(), model)


class OpenAIProvider(LLMProvider):
    """OpenAI API provider (GPT-4, GPT-3.5, etc.)."""

    BASE_URL = "https://api.openai.com/v1/chat/completions"

    @property
    def provider_name(self) -> str:
        return "openai"

    def _build_request(
        self,
        messages: List[ChatMessage],
        model: str,
        params: Dict,
    ) -> tuple[str, Dict, Dict]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            **params,
        }
        return self.BASE_URL, headers, body

    def _parse_response(self, data: Dict, model: str) -> LLMResponse:
        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model", model),
            provider=self.provider_name,
            usage=data.get("usage", {}),
            raw_response=data,
        )


class AnthropicProvider(LLMProvider):
    """Anthropic API provider (Claude models)."""

    BASE_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def _build_request(
        self,
        messages: List[ChatMessage],
        model: str,
        params: Dict,
    ) -> tuple[str, Dict, Dict]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "Content-Type": "application/json",
        }
        # Anthropic requires system message separate from messages
        system_msg = None
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_msg = m.content
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        body = {
            "model": model,
            "messages": chat_messages,
            "max_tokens": params.pop("max_tokens", 4096),
            **params,
        }
        if system_msg:
            body["system"] = system_msg

        return self.BASE_URL, headers, body

    def _parse_response(self, data: Dict, model: str) -> LLMResponse:
        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")
        return LLMResponse(
            content=content,
            model=data.get("model", model),
            provider=self.provider_name,
            usage=data.get("usage", {}),
            raw_response=data,
        )


class DeepSeekProvider(LLMProvider):
    """DeepSeek API provider (OpenAI-compatible)."""

    BASE_URL = "https://api.deepseek.com/v1/chat/completions"

    @property
    def provider_name(self) -> str:
        return "deepseek"

    def _build_request(
        self,
        messages: List[ChatMessage],
        model: str,
        params: Dict,
    ) -> tuple[str, Dict, Dict]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            **params,
        }
        return self.BASE_URL, headers, body

    def _parse_response(self, data: Dict, model: str) -> LLMResponse:
        return LLMResponse(
            content=data["choices"][0]["message"]["content"],
            model=data.get("model", model),
            provider=self.provider_name,
            usage=data.get("usage", {}),
            raw_response=data,
        )


# --- Provider Factory ---

PROVIDER_MAP = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "deepseek": DeepSeekProvider,
}

# Model prefix → provider mapping
MODEL_PROVIDER_MAP = {
    "gpt-": "openai",
    "o1": "openai",
    "claude-": "anthropic",
    "deepseek-": "deepseek",
}


def detect_provider(model: str) -> str:
    """Detect the provider from a model name."""
    for prefix, provider in MODEL_PROVIDER_MAP.items():
        if model.startswith(prefix):
            return provider
    raise LLMError(f"Cannot detect provider for model: {model}")


def create_provider(
    provider_name: str,
    api_key: str,
    **kwargs,
) -> LLMProvider:
    """Create an LLM provider instance.

    Args:
        provider_name: One of 'openai', 'anthropic', 'deepseek'.
        api_key: The API key for the provider.
        **kwargs: Additional arguments (max_retries, retry_delay, timeout).
    """
    cls = PROVIDER_MAP.get(provider_name)
    if not cls:
        raise LLMError(f"Unknown provider: {provider_name}. Available: {list(PROVIDER_MAP.keys())}")
    return cls(api_key=api_key, **kwargs)


def resolve_llm_call(db: Session) -> Callable[[str, List[ChatMessage]], str]:
    """Create an LLM callable that uses stored API keys, with env var fallback.

    Used by meetings API, WebSocket handler, and background runner.
    """
    from app.config import settings
    from app.models import APIKey
    from app.core.encryption import decrypt_api_key

    env_keys = {
        "openai": settings.OPENAI_API_KEY,
        "anthropic": settings.ANTHROPIC_API_KEY,
        "deepseek": settings.DEEPSEEK_API_KEY,
    }
    model_map = {
        "openai": "gpt-4",
        "anthropic": "claude-3-opus-20240229",
        "deepseek": "deepseek-chat",
    }

    def llm_call(system_prompt: str, messages: List[ChatMessage]) -> str:
        last_error: Exception | None = None
        for provider_name in ["deepseek", "anthropic", "openai"]:
            api_key_record = (
                db.query(APIKey)
                .filter(APIKey.provider == provider_name, APIKey.is_active == True)
                .first()
            )
            if api_key_record:
                key = decrypt_api_key(api_key_record.encrypted_key, settings.ENCRYPTION_SECRET)
            else:
                key = env_keys.get(provider_name, "")
            if key:
                try:
                    provider = create_provider(provider_name, key)
                    all_messages = [ChatMessage(role="system", content=system_prompt)] + list(messages)
                    response = provider.chat(all_messages, model_map[provider_name])
                    return response.content
                except Exception as e:
                    last_error = e
                    import logging
                    logging.getLogger(__name__).warning(
                        "Provider %s failed, trying next: %s", provider_name, e
                    )
                    continue
        if last_error:
            raise last_error
        raise RuntimeError(
            "No active API key found for any LLM provider. Add one in Settings or set environment variables."
        )

    return llm_call
