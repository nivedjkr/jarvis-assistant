"""
Google OAuth2 Helper for JARVIS (Calendar & Gmail)
Manages authentication tokens and API service initialization.
"""

import os
from pathlib import Path
from typing import Optional, List

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES: List[str] = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify"
]


class GoogleAuthManager:
    """Manages OAuth2 token storage and Google API authentication."""

    def __init__(self, data_dir: str = "jarvis/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.token_path = self.data_dir / "google_token.json"
        
        # Check root or data_dir for credentials.json
        self.credentials_path = Path("credentials.json")
        if not self.credentials_path.exists():
            self.credentials_path = self.data_dir / "credentials.json"

    def get_credentials(self) -> Optional[Credentials]:
        """
        Retrieve valid Google OAuth2 credentials.
        Refreshes expired tokens if possible.
        Returns None if credentials.json or token is missing/unconfigured/unrefreshable.
        """
        creds = None
        if self.token_path.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_path))
            except Exception:
                creds = None

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(self.token_path, "w", encoding="utf-8") as token_file:
                    token_file.write(creds.to_json())
                return creds
            except Exception:
                creds = None

        return creds

    def is_authenticated(self) -> bool:
        """Check if valid Google credentials are ready for use."""
        creds = self.get_credentials()
        return creds is not None and creds.valid

    def has_calendar_write_scope(self) -> bool:
        """Check if the active credentials possess Google Calendar write permissions."""
        creds = self.get_credentials()
        if not creds or not creds.valid:
            return False
        write_scope = "https://www.googleapis.com/auth/calendar"
        if hasattr(creds, 'has_scopes'):
            try:
                return creds.has_scopes([write_scope])
            except Exception:
                pass
        if hasattr(creds, 'scopes') and creds.scopes:
            return write_scope in creds.scopes
        return True

    def authenticate_interactive(self) -> tuple[bool, str]:
        """
        Run interactive browser OAuth2 authentication flow.
        Requires credentials.json downloaded from Google Cloud Console.
        """
        if not self.credentials_path.exists():
            return False, "credentials.json not found in root directory or jarvis/data/. Download OAuth Client ID credentials from Google Cloud Console."

        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
            with open(self.token_path, "w", encoding="utf-8") as token_file:
                token_file.write(creds.to_json())
            return True, "Google OAuth2 authentication successful."
        except Exception as e:
            return False, f"Authentication error: {str(e)}"
