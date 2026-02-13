import json
import logging
import pytest


class TestLoggingMiddleware:
    def test_response_time_header(self, client):
        """Responses include X-Response-Time header."""
        resp = client.get("/")
        assert "X-Response-Time" in resp.headers
        assert resp.headers["X-Response-Time"].endswith("ms")

    def test_successful_request_logged(self, client, caplog):
        """Successful requests are logged at INFO level."""
        with caplog.at_level(logging.INFO, logger="app.access"):
            client.get("/")

        log_records = [r for r in caplog.records if r.name == "app.access"]
        assert len(log_records) >= 1
        log_data = json.loads(log_records[-1].message)
        assert log_data["method"] == "GET"
        assert log_data["path"] == "/"
        assert log_data["status"] == 200
        assert "duration_ms" in log_data

    def test_404_logged_as_warning(self, client, caplog):
        """4xx responses are logged at WARNING level."""
        with caplog.at_level(logging.WARNING, logger="app.access"):
            client.get("/api/teams/nonexistent-id")

        log_records = [r for r in caplog.records if r.name == "app.access" and r.levelno == logging.WARNING]
        assert len(log_records) >= 1
        log_data = json.loads(log_records[-1].message)
        assert log_data["status"] == 404

    def test_query_params_logged(self, client, caplog):
        """Query parameters are included in log data."""
        with caplog.at_level(logging.INFO, logger="app.access"):
            client.get("/api/search/teams", params={"q": "test"})

        log_records = [r for r in caplog.records if r.name == "app.access"]
        found = False
        for record in log_records:
            data = json.loads(record.message)
            if data.get("path") == "/api/search/teams" and "query" in data:
                assert "q=test" in data["query"]
                found = True
                break
        assert found

    def test_log_contains_client_ip(self, client, caplog):
        """Log entries include client IP."""
        with caplog.at_level(logging.INFO, logger="app.access"):
            client.get("/")

        log_records = [r for r in caplog.records if r.name == "app.access"]
        assert len(log_records) >= 1
        log_data = json.loads(log_records[-1].message)
        assert "client_ip" in log_data
