"""
Simple symmetric encryption for API key storage using Fernet.

The encryption key is derived from a secret configured in settings.
In production, use a proper secrets manager.
"""

import base64
import hashlib

from cryptography.fernet import Fernet


def _derive_key(secret: str) -> bytes:
    """Derive a Fernet-compatible key from an arbitrary secret string."""
    digest = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_api_key(api_key: str, secret: str) -> str:
    """Encrypt an API key using the given secret."""
    f = Fernet(_derive_key(secret))
    return f.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str, secret: str) -> str:
    """Decrypt an API key using the given secret."""
    f = Fernet(_derive_key(secret))
    return f.decrypt(encrypted_key.encode()).decode()
