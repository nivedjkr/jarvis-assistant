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


def test_google_auth_interactive_state_consistency(tmp_path):
    auth_mgr = GoogleAuthManager(data_dir=str(tmp_path))
    fake_creds_path = tmp_path / "credentials.json"
    fake_creds_path.write_text(json.dumps({
        "installed": {
            "client_id": "fake_id",
            "client_secret": "fake_secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }))
    auth_mgr.credentials_path = fake_creds_path

    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.to_json.return_value = '{"token": "xyz"}'

    with patch("google_auth_oauthlib.flow.InstalledAppFlow.run_local_server", return_value=mock_creds) as mock_rls:
        ok, msg = auth_mgr.authenticate_interactive(port=8080)
        assert ok is True
        assert "successful" in msg
        mock_rls.assert_called_once()
        _, kwargs = mock_rls.call_args
        assert kwargs.get("open_browser") is True
        assert hasattr(kwargs.get("authorization_prompt_message"), "format")

