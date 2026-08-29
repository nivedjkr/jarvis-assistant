import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from jarvis.api import app, PSUTIL_AVAILABLE, START_TIME


def test_vitals_endpoint_non_blocking_structure():
    """
    FIX 1 Test:
    Verify that /vitals returns a valid 200 JSON payload containing non-zero or structured
    system vitals metrics, non-blocking CPU percentage, and valid uptime.
    """
    client = TestClient(app)
    response = client.get("/vitals")
    assert response.status_code == 200

    data = response.json()
    assert "cpu_usage" in data
    assert "ram_usage" in data
    assert "cpu_pct" in data
    assert "ram_pct" in data
    assert "uptime_seconds" in data
    assert "commands_today" in data
    assert "tool_calls_today" in data
    assert isinstance(data["uptime_seconds"], int)
    assert data["uptime_seconds"] >= 0


def test_sent_email_endpoint():
    """
    FIX 4 Test:
    Verify that /email/sent (and /api/email/sent) returns a structured JSON payload with status: 'ok'
    and a list under 'sent_emails'.
    """
    client = TestClient(app)

    mock_sent_emails = [
        {
            "id": "msg_001",
            "recipient": "test@domain.com",
            "subject": "Executive Briefing",
            "date": "Sat, 29 Aug 2026 22:00:00 GMT",
            "snippet": "Here is the weekly update..."
        }
    ]

    with patch("jarvis.email_service.EmailService.fetch_sent_messages", return_value=mock_sent_emails):
        res1 = client.get("/email/sent")
        assert res1.status_code == 200
        d1 = res1.json()
        assert d1.get("status") == "ok"
        assert d1.get("sent_emails") == mock_sent_emails

        res2 = client.get("/api/email/sent")
        assert res2.status_code == 200
        d2 = res2.json()
        assert d2.get("status") == "ok"
        assert d2.get("sent_emails") == mock_sent_emails
