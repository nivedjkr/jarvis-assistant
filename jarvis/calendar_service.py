"""
Google Calendar Sync Module for JARVIS
Fetches real calendar events using Google Calendar API v3.
Implements 5-minute maximum cache and proactive event notifications.
"""

import time
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple
from googleapiclient.discovery import build

from jarvis.google_auth import GoogleAuthManager


class CalendarService:
    """Manages Google Calendar API queries and event reminders."""

    def __init__(self, auth_manager: GoogleAuthManager):
        self.auth_manager = auth_manager
        self.cached_events: List[Dict[str, Any]] = []
        self.last_fetch_time: float = 0.0
        self.cache_ttl_seconds: float = 300.0  # 5 minutes maximum
        self.alerted_events: set = set()  # Track (event_id, minutes_before) to avoid duplicate alerts

    def _get_service(self):
        """Initialize Google Calendar API service client."""
        creds = self.auth_manager.get_credentials()
        if not creds:
            return None
        try:
            return build("calendar", "v3", credentials=creds)
        except Exception:
            return None

    def fetch_upcoming_events(self, force_refresh: bool = False, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch real events from Google Calendar.
        Enforces maximum 5-minute cache policy.
        """
        now_ts = time.time()
        if not force_refresh and (now_ts - self.last_fetch_time) < self.cache_ttl_seconds and self.cached_events:
            return self.cached_events

        service = self._get_service()
        if not service:
            return []

        try:
            now_iso = datetime.utcnow().isoformat() + "Z"
            events_result = service.events().list(
                calendarId="primary",
                timeMin=now_iso,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime"
            ).execute()

            items = events_result.get("items", [])
            events = []
            for item in items:
                start = item.get("start", {})
                end = item.get("end", {})
                start_str = start.get("dateTime", start.get("date"))
                end_str = end.get("dateTime", end.get("date"))
                
                events.append({
                    "id": item.get("id"),
                    "summary": item.get("summary", "Untitled Event"),
                    "start": start_str,
                    "end": end_str,
                    "location": item.get("location", ""),
                    "description": item.get("description", ""),
                    "raw": item
                })

            self.cached_events = events
            self.last_fetch_time = now_ts
            return events
        except Exception:
            return []

    def get_events_for_day(self, target_date: date) -> List[Dict[str, Any]]:
        """Fetch all real events scheduled for a specific date."""
        service = self._get_service()
        if not service:
            return []

        try:
            time_min = datetime.combine(target_date, datetime.min.time()).isoformat() + "Z"
            time_max = datetime.combine(target_date, datetime.max.time()).isoformat() + "Z"

            events_result = service.events().list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime"
            ).execute()

            items = events_result.get("items", [])
            events = []
            for item in items:
                start = item.get("start", {})
                end = item.get("end", {})
                start_str = start.get("dateTime", start.get("date"))
                end_str = end.get("dateTime", end.get("date"))

                events.append({
                    "id": item.get("id"),
                    "summary": item.get("summary", "Untitled Event"),
                    "start": start_str,
                    "end": end_str,
                    "location": item.get("location", "")
                })
            return events
        except Exception:
            return []

    def get_today_summary(self) -> str:
        """Generate boot greeting calendar summary string for today."""
        if not self.auth_manager.is_authenticated():
            return ""

        today_events = self.get_events_for_day(date.today())
        if not today_events:
            return "No calendar events scheduled for today."

        count = len(today_events)
        first_event = today_events[0]
        start_str = first_event["start"]

        time_part = ""
        try:
            if "T" in start_str:
                dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                time_part = f", first at {dt.strftime('%H:%M')}"
        except Exception:
            pass

        return f"{count} event{'s' if count > 1 else ''} today{time_part}."

    def get_next_event(self) -> Optional[Dict[str, Any]]:
        """Retrieve the next upcoming event."""
        events = self.fetch_upcoming_events(force_refresh=True)
        return events[0] if events else None

    def evaluate_upcoming_alerts(self) -> List[str]:
        """
        Check for upcoming events starting in ~10 minutes or ~2 minutes.
        Returns spoken alert strings.
        """
        if not self.auth_manager.is_authenticated():
            return []

        events = self.fetch_upcoming_events(force_refresh=False)
        alerts = []
        now = datetime.now()

        for event in events:
            start_str = event["start"]
            event_id = event["id"]
            if not start_str or "T" not in start_str:
                continue

            try:
                # Parse datetime with ISO offset or Z
                clean_start = start_str.replace("Z", "+00:00")
                start_dt = datetime.fromisoformat(clean_start).replace(tzinfo=None)
                diff_minutes = (start_dt - now).total_seconds() / 60.0

                # 10 minute warning (between 9.0 and 11.0 mins)
                if 8.5 <= diff_minutes <= 11.0:
                    alert_key = (event_id, 10)
                    if alert_key not in self.alerted_events:
                        self.alerted_events.add(alert_key)
                        alerts.append(f"Sir, your {event['summary']} starts in 10 minutes.")

                # 2 minute warning (between 1.0 and 3.0 mins)
                elif 0.5 <= diff_minutes <= 3.0:
                    alert_key = (event_id, 2)
                    if alert_key not in self.alerted_events:
                        self.alerted_events.add(alert_key)
                        alerts.append(f"Sir, your {event['summary']} starts in 2 minutes.")
            except Exception:
                continue

        return alerts

    def format_calendar_command(self, mode: str = "today") -> str:
        """Format output for /calendar today, /calendar tomorrow, /calendar next."""
        if not self.auth_manager.is_authenticated():
            return "Google Calendar is not authenticated. Please run Google OAuth setup or place credentials.json in workspace."

        if mode == "next":
            evt = self.get_next_event()
            if not evt:
                return "No upcoming events found on your Google Calendar, sir."
            start_str = evt["start"]
            time_formatted = start_str
            try:
                if "T" in start_str:
                    dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    time_formatted = dt.strftime("%A, %b %d at %H:%M")
            except Exception:
                pass
            loc_str = f" (Location: {evt['location']})" if evt.get("location") else ""
            return f"Next Event: '{evt['summary']}' starting {time_formatted}{loc_str}."

        target_date = date.today() if mode == "today" else (date.today() + timedelta(days=1))
        events = self.get_events_for_day(target_date)

        day_label = "Today" if mode == "today" else "Tomorrow"
        if not events:
            return f"No events scheduled for {day_label.lower()}, sir."

        lines = [f"=== Google Calendar ({day_label}: {target_date.strftime('%Y-%m-%d')}) ==="]
        for idx, evt in enumerate(events, 1):
            start_str = evt["start"]
            time_part = start_str
            try:
                if "T" in start_str:
                    dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    time_part = dt.strftime("%H:%M")
            except Exception:
                pass
            loc = f" — {evt['location']}" if evt.get("location") else ""
            lines.append(f"{idx}. [{time_part}] {evt['summary']}{loc}")

        return "\n".join(lines)
