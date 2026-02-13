import pytest
from unittest.mock import patch, MagicMock
from app.core.webhook_dispatcher import dispatch_webhook, _compute_signature


class TestWebhookCRUD:
    def test_list_events(self, client):
        """List supported webhook events."""
        resp = client.get("/api/webhooks/events")
        assert resp.status_code == 200
        events = resp.json()
        assert "meeting.completed" in events
        assert "artifact.created" in events

    def test_create_webhook(self, client):
        """Create a webhook registration."""
        resp = client.post("/api/webhooks/", json={
            "url": "https://example.com/hook",
            "events": ["meeting.completed"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["url"] == "https://example.com/hook"
        assert data["events"] == ["meeting.completed"]
        assert data["is_active"] is True

    def test_create_webhook_invalid_event(self, client):
        """Reject webhook with invalid event type."""
        resp = client.post("/api/webhooks/", json={
            "url": "https://example.com/hook",
            "events": ["invalid.event"],
        })
        assert resp.status_code == 400
        assert "invalid.event" in resp.json()["detail"]

    def test_list_webhooks(self, client):
        """List all webhooks."""
        client.post("/api/webhooks/", json={
            "url": "https://a.com/hook",
            "events": ["meeting.completed"],
        })
        client.post("/api/webhooks/", json={
            "url": "https://b.com/hook",
            "events": ["artifact.created"],
        })
        resp = client.get("/api/webhooks/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_webhook(self, client):
        """Get a specific webhook."""
        create = client.post("/api/webhooks/", json={
            "url": "https://example.com/hook",
            "events": ["meeting.completed"],
        }).json()
        resp = client.get(f"/api/webhooks/{create['id']}")
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://example.com/hook"

    def test_update_webhook(self, client):
        """Update a webhook."""
        create = client.post("/api/webhooks/", json={
            "url": "https://example.com/hook",
            "events": ["meeting.completed"],
        }).json()
        resp = client.put(f"/api/webhooks/{create['id']}", json={
            "is_active": False,
            "events": ["meeting.completed", "artifact.created"],
        })
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False
        assert len(resp.json()["events"]) == 2

    def test_delete_webhook(self, client):
        """Delete a webhook."""
        create = client.post("/api/webhooks/", json={
            "url": "https://example.com/hook",
            "events": ["meeting.completed"],
        }).json()
        resp = client.delete(f"/api/webhooks/{create['id']}")
        assert resp.status_code == 204
        assert client.get(f"/api/webhooks/{create['id']}").status_code == 404

    def test_get_nonexistent(self, client):
        """Get nonexistent webhook returns 404."""
        assert client.get("/api/webhooks/fake").status_code == 404


class TestWebhookDispatcher:
    def test_compute_signature(self):
        """HMAC signature is deterministic."""
        sig1 = _compute_signature("payload", "secret")
        sig2 = _compute_signature("payload", "secret")
        assert sig1 == sig2
        assert len(sig1) == 64  # SHA-256 hex

    def test_different_payload_different_sig(self):
        """Different payloads produce different signatures."""
        sig1 = _compute_signature("payload1", "secret")
        sig2 = _compute_signature("payload2", "secret")
        assert sig1 != sig2

    @patch("app.core.webhook_dispatcher.httpx.Client")
    @patch("app.core.webhook_dispatcher.SessionLocal")
    def test_dispatch_calls_matching_webhooks(self, mock_session_cls, mock_client_cls):
        """Dispatcher sends POST to webhooks matching the event."""
        mock_db = MagicMock()
        mock_session_cls.return_value = mock_db

        mock_webhook = MagicMock()
        mock_webhook.id = "wh1"
        mock_webhook.url = "https://example.com/hook"
        mock_webhook.events = ["meeting.completed"]
        mock_webhook.is_active = True
        mock_webhook.secret = None

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_webhook]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_http = MagicMock()
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)
        mock_http.post.return_value = mock_response
        mock_client_cls.return_value = mock_http

        dispatch_webhook("meeting.completed", {"meeting_id": "123"})

        mock_http.post.assert_called_once()
        call_args = mock_http.post.call_args
        assert call_args[0][0] == "https://example.com/hook"
