import os
import re
import pytest
from fastapi.testclient import TestClient
from jarvis.api import app, get_host_binding, ALLOW_ORIGIN_REGEX, ALLOWED_ORIGINS

def test_host_binding_default(monkeypatch):
    monkeypatch.delenv("JARVIS_ALLOW_REMOTE", raising=False)
    assert get_host_binding() == "127.0.0.1"

def test_host_binding_remote_enabled(monkeypatch):
    monkeypatch.setenv("JARVIS_ALLOW_REMOTE", "true")
    assert get_host_binding() == "0.0.0.0"

    monkeypatch.setenv("JARVIS_ALLOW_REMOTE", "1")
    assert get_host_binding() == "0.0.0.0"

def test_cors_origin_regex():
    pattern = re.compile(ALLOW_ORIGIN_REGEX)
    
    # Valid origins
    assert pattern.match("http://localhost:3000")
    assert pattern.match("http://127.0.0.1:8765")
    assert pattern.match("http://100.64.1.25:8765")      # Tailscale IP
    assert pattern.match("http://100.115.22.105")       # Tailscale IP
    assert pattern.match("http://192.168.1.50:8765")    # Local LAN IP
    assert pattern.match("http://10.0.0.15:8765")       # Local LAN IP
    assert pattern.match("http://jarvis-pc.tail1234.ts.net:8765") # Tailscale domain
    assert pattern.match("https://myhost.ts.net")

    # Invalid public origins
    assert not pattern.match("http://malicious-website.com")
    assert not pattern.match("http://8.8.8.8")
    assert not pattern.match("http://example.com:8765")

def test_websocket_token_rejection():
    client = TestClient(app)
    with client.websocket_connect("/ws?token=invalid_token") as websocket:
        # Client sends invalid auth JSON
        websocket.send_json({"type": "auth", "token": "wrong"})
        data = websocket.receive_json()
        assert data.get("type") == "error"
        assert "Authentication failed" in data.get("message", "")

def test_websocket_token_valid():
    client = TestClient(app)
    ws_token = os.getenv("JARVIS_WS_TOKEN", "jarvis_secure_local_token_2026")
    with client.websocket_connect(f"/ws?token={ws_token}") as websocket:
        data = websocket.receive_json()
        assert data.get("type") == "status"
        assert data.get("status") == "connected"

def test_mobile_static_endpoint():
    client = TestClient(app)
    response = client.get("/mobile/")
    assert response.status_code == 200
    assert "JARVIS Mobile" in response.text
