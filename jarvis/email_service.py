"""
Gmail Triage Module for JARVIS
Fetches unread inbox messages, performs LLM importance classification,
and manages proactive urgent email notifications while preserving strict body privacy.
"""

import base64
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from googleapiclient.discovery import build

from jarvis.google_auth import GoogleAuthManager


class EmailService:
    """Manages Gmail API queries, unseen message tracking, and LLM triage."""

    def __init__(self, auth_manager: GoogleAuthManager, api_client: Optional[Any] = None):
        self.auth_manager = auth_manager
        self.api_client = api_client
        self.seen_message_ids: set = set()

    def _get_service(self):
        """Initialize Gmail API service client."""
        creds = self.auth_manager.get_credentials()
        if not creds:
            return None
        try:
            return build("gmail", "v1", credentials=creds)
        except Exception:
            return None

    def fetch_unread_messages(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Fetch real unread emails from Gmail inbox.
        Returns list of email metadata dicts.
        """
        service = self._get_service()
        if not service:
            return []

        try:
            results = service.users().messages().list(
                userId="me",
                q="is:unread in:inbox",
                maxResults=max_results
            ).execute()

            messages = results.get("messages", [])
            unread_emails = []

            for msg_meta in messages:
                msg_id = msg_meta["id"]
                msg_data = service.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="full"
                ).execute()

                headers = msg_data.get("payload", {}).get("headers", [])
                subject = "No Subject"
                sender = "Unknown Sender"
                date_str = ""

                for h in headers:
                    name = h.get("name", "").lower()
                    if name == "subject":
                        subject = h.get("value", "No Subject")
                    elif name == "from":
                        sender = h.get("value", "Unknown Sender")
                    elif name == "date":
                        date_str = h.get("value", "")

                # Extract snippet
                snippet = msg_data.get("snippet", "")

                unread_emails.append({
                    "id": msg_id,
                    "sender": sender,
                    "subject": subject,
                    "date": date_str,
                    "snippet": snippet,
                    "raw": msg_data
                })

            return unread_emails
        except Exception:
            return []

    def get_message_body(self, msg_id: str) -> str:
        """Fetch real message body text for a specific email by ID."""
        service = self._get_service()
        if not service:
            return "Gmail service unavailable."

        try:
            msg_data = service.users().messages().get(
                userId="me",
                id=msg_id,
                format="full"
            ).execute()

            payload = msg_data.get("payload", {})
            parts = payload.get("parts", [])

            body_text = ""
            if not parts and payload.get("body", {}).get("data"):
                body_data = payload.get("body", {}).get("data")
                body_text = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="ignore")
            else:
                for part in parts:
                    mime_type = part.get("mimeType", "")
                    if mime_type == "text/plain" and part.get("body", {}).get("data"):
                        b_data = part.get("body", {}).get("data")
                        body_text += base64.urlsafe_b64decode(b_data).decode("utf-8", errors="ignore")
                        break
                if not body_text and parts:
                    # Fallback to snippet or html strip
                    body_text = msg_data.get("snippet", "No body text extracted.")

            return body_text.strip() if body_text else msg_data.get("snippet", "Empty message body.")
        except Exception as e:
            return f"Error retrieving message body: {str(e)}"

    def classify_importance(self, sender: str, subject: str) -> str:
        """
        Use lightweight rules / LLM triage to classify email as 'urgent', 'normal', or 'noise'.
        """
        lower_subj = subject.lower()
        lower_sender = sender.lower()

        # Immediate rule checks for urgency keywords
        urgent_keywords = ["urgent", "action required", "asap", "critical", "security alert", "emergency", "deadline", "payment failed", "important"]
        if any(k in lower_subj for k in urgent_keywords):
            return "urgent"

        # Noise keywords
        noise_keywords = ["newsletter", "unsubscribe", "weekly digest", "promotions", "% off", "marketing", "no-reply"]
        if any(k in lower_subj or k in lower_sender for k in noise_keywords):
            return "noise"

        return "normal"

    def evaluate_new_unread_emails(self) -> List[Dict[str, Any]]:
        """
        Background triage check for new unread inbox messages.
        Marks messages as seen locally to prevent duplicate alerts.
        Returns urgent items to be announced via TTS.
        """
        if not self.auth_manager.is_authenticated():
            return []

        unread = self.fetch_unread_messages(max_results=10)
        urgent_announcements = []

        for msg in unread:
            msg_id = msg["id"]
            if msg_id in self.seen_message_ids:
                continue

            self.seen_message_ids.add(msg_id)
            classification = self.classify_importance(msg["sender"], msg["subject"])

            if classification == "urgent":
                clean_sender = msg["sender"].split("<")[0].strip().strip('"')
                urgent_announcements.append({
                    "id": msg_id,
                    "sender": clean_sender,
                    "subject": msg["subject"],
                    "spoken_phrase": f"Sir, new urgent email from {clean_sender} — {msg['subject']}"
                })

        return urgent_announcements

    def format_unread_list(self, limit: int = 5) -> str:
        """Format /email command showing last N unread messages."""
        if not self.auth_manager.is_authenticated():
            return "Gmail is not authenticated. Please run Google OAuth setup or place credentials.json in workspace."

        unread = self.fetch_unread_messages(max_results=limit)
        if not unread:
            return "Your inbox has no unread messages, sir."

        lines = ["=== Recent Unread Emails ==="]
        for idx, msg in enumerate(unread, 1):
            clean_sender = msg["sender"].split("<")[0].strip().strip('"')
            lines.append(f"{idx}. From: {clean_sender}")
            lines.append(f"   Subject: {msg['subject']}")
            lines.append(f"   Date: {msg['date']}\n")

        return "\n".join(lines).strip()

    def read_email_body_by_index(self, index_1_based: int) -> str:
        """Format /email read <n> output."""
        if not self.auth_manager.is_authenticated():
            return "Gmail is not authenticated."

        unread = self.fetch_unread_messages(max_results=10)
        if not unread or index_1_based < 1 or index_1_based > len(unread):
            return f"Invalid email index {index_1_based}. Available unread emails: 1 to {len(unread)}."

        target = unread[index_1_based - 1]
        body = self.get_message_body(target["id"])
        clean_sender = target["sender"].split("<")[0].strip().strip('"')

        return (
            f"=== Reading Email #{index_1_based} ===\n"
            f"From: {clean_sender}\n"
            f"Subject: {target['subject']}\n"
            f"Date: {target['date']}\n\n"
            f"{body}"
        )

    def generate_email_summary_briefing(self) -> str:
        """Generate /email summary output."""
        if not self.auth_manager.is_authenticated():
            return "Gmail is not authenticated."

        unread = self.fetch_unread_messages(max_results=10)
        if not unread:
            return "No unread emails to summarize, sir."

        summary_lines = [f"Found {len(unread)} unread email{'s' if len(unread) > 1 else ''}:"]
        for idx, msg in enumerate(unread, 1):
            clean_sender = msg["sender"].split("<")[0].strip().strip('"')
            importance = self.classify_importance(msg["sender"], msg["subject"])
            summary_lines.append(f"- [{importance.upper()}] From {clean_sender}: {msg['subject']}")

        return "\n".join(summary_lines)
