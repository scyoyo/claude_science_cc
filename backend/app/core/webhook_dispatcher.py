"""Webhook dispatcher: sends HTTP POST to registered webhook URLs."""

import hashlib
import hmac
import json
import logging
from typing import Any, Dict

import httpx

from app.database import SessionLocal
from app.models import WebhookConfig

logger = logging.getLogger("app.webhooks")


def _compute_signature(payload: str, secret: str) -> str:
    """Compute HMAC-SHA256 signature for webhook payload."""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def dispatch_webhook(event: str, data: Dict[str, Any]):
    """Send webhook notifications for the given event.

    Args:
        event: Event type (e.g., "meeting.completed")
        data: Event payload data
    """
    db = SessionLocal()
    try:
        webhooks = db.query(WebhookConfig).filter(
            WebhookConfig.is_active == True,
        ).all()

        for webhook in webhooks:
            if event not in (webhook.events or []):
                continue

            payload = json.dumps({"event": event, "data": data})
            headers = {"Content-Type": "application/json"}

            if webhook.secret:
                headers["X-Webhook-Signature"] = _compute_signature(payload, webhook.secret)

            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(webhook.url, content=payload, headers=headers)
                logger.info(f"Webhook {webhook.id} -> {webhook.url}: {resp.status_code}")
            except Exception as e:
                logger.error(f"Webhook {webhook.id} -> {webhook.url} failed: {e}")
    finally:
        db.close()
