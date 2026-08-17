import pytest
import os
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from google.auth.exceptions import RefreshError

from jarvis.google_auth import GoogleAuthManager
from jarvis.tools import ToolRegistry


def test_google_auth_token_status(tmp_path):
    auth_mgr = GoogleAuthManager(data_dir=str(tmp_path))
    auth_mgr.credentials_path = tmp_path / "credentials.json"
    status = auth_mgr.get_token_status()
    
    assert status["has_credentials_json"] is False
    assert status["has_token_file"] is False
    assert status["is_valid"] is False
    assert "missing" in status["message"].lower()


def test_google_auth_auto_purge_invalid_token(tmp_path):
    token_file = tmp_path / "google_token.json"
    fake_token = {
        "token": "fake_access_token",
        "refresh_token": "fake_refresh_token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "fake_client_id",
        "client_secret": "fake_secret",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
        "expiry": "2020-01-01T00:00:00Z"
    }
    with open(token_file, "w") as f:
        json.dump(fake_token, f)

    auth_mgr = GoogleAuthManager(data_dir=str(tmp_path))
    assert auth_mgr.token_path.exists()

    with patch("google.oauth2.credentials.Credentials.refresh", side_effect=RefreshError("invalid_grant")):
        creds = auth_mgr.get_credentials()
        assert creds is None
        # Verify invalid token file was automatically unlinked/purged
        assert not auth_mgr.token_path.exists()


def test_authenticate_google_tool_registered():
    registry = ToolRegistry()
    assert "authenticate_google" in registry.tools
