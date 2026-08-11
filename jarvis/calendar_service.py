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
        """Generate boot greeting calendar summary string for today without blocking startup."""
        if not self.auth_manager.is_authenticated():
            return ""

        now_ts = time.time()
        # Return cached events if available to eliminate network delay at boot
        if self.cached_events and (now_ts - self.last_fetch_time) < self.cache_ttl_seconds:
            today_str = str(date.today())
            today_events = [e for e in self.cached_events if str(e.get("start", "")).startswith(today_str)]
        else:
            try:
                today_events = self.get_events_for_day(date.today())
            except Exception:
                return ""

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
                start_dt = datetime.fromisoformat(clean_start)
                if start_dt.tzinfo is not None:
                    start_dt = start_dt.astimezone().replace(tzinfo=None)
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

    def _invalidate_cache(self):
        """Invalidate events cache after mutations."""
        self.cached_events = []
        self.last_fetch_time = 0.0

    def create_event(
        self,
        summary: str,
        start_time: str,
        end_time: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        timezone: str = "UTC"
    ) -> Dict[str, Any]:
        """
        Create a new Google Calendar event.
        start_time and end_time accept ISO strings (e.g. '2026-08-09T18:00:00') or date strings ('2026-08-09').
        """
        service = self._get_service()
        if not service:
            return {"error": "Google Calendar is not authenticated."}

        if self.auth_manager and hasattr(self.auth_manager, 'has_calendar_write_scope'):
            if not self.auth_manager.has_calendar_write_scope():
                return {
                    "error": (
                        "INSUFFICIENT OAUTH PERMISSIONS: Your active Google token only has read access. "
                        "To create, edit, or delete events, please re-authenticate Google OAuth with full calendar scope by running '/calendar auth' in CLI or deleting jarvis/data/google_token.json."
                    )
                }

        # Auto-correct past years (e.g. LLM default 2023 -> current year 2026)
        current_year = datetime.now().year
        try:
            year_str = start_time[:4]
            if year_str.isdigit():
                start_year = int(year_str)
                if start_year < current_year:
                    start_time = str(current_year) + start_time[4:]
                    if end_time and end_time[:4].isdigit() and int(end_time[:4]) < current_year:
                        end_time = str(current_year) + end_time[4:]
        except Exception:
            pass

        body: Dict[str, Any] = {
            "summary": summary
        }
        if location:
            body["location"] = location
        if description:
            body["description"] = description

        # Handle start time format
        if "T" in start_time:
            body["start"] = {"dateTime": start_time if start_time.endswith("Z") or "+" in start_time else start_time + "Z"}
        else:
            body["start"] = {"date": start_time}

        # Handle end time format or default (+1h for dateTime, same day for date)
        if end_time:
            if "T" in end_time:
                body["end"] = {"dateTime": end_time if end_time.endswith("Z") or "+" in end_time else end_time + "Z"}
            else:
                body["end"] = {"date": end_time}
        else:
            if "dateTime" in body["start"]:
                try:
                    dt = datetime.fromisoformat(body["start"]["dateTime"].replace("Z", "+00:00"))
                    end_dt = dt + timedelta(hours=1)
                    body["end"] = {"dateTime": end_dt.isoformat()}
                except Exception:
                    body["end"] = body["start"]
            else:
                body["end"] = body["start"]

        if attendees:
            body["attendees"] = [{"email": email} for email in attendees if isinstance(email, str)]

        try:
            created_event = service.events().insert(
                calendarId="primary",
                body=body
            ).execute()
            self._invalidate_cache()
            return {
                "id": created_event.get("id"),
                "summary": created_event.get("summary"),
                "start": created_event.get("start", {}).get("dateTime", created_event.get("start", {}).get("date")),
                "end": created_event.get("end", {}).get("dateTime", created_event.get("end", {}).get("date")),
                "location": created_event.get("location", ""),
                "description": created_event.get("description", ""),
                "htmlLink": created_event.get("htmlLink", "")
            }
        except Exception as e:
            err_str = str(e)
            if "insufficientPermissions" in err_str or "403" in err_str:
                return {
                    "error": (
                        "INSUFFICIENT OAUTH PERMISSIONS: Google Calendar returned HTTP 403 Insufficient Permission. "
                        "Your saved token does not have event creation access. Please re-authenticate by running '/calendar auth' in CLI or deleting jarvis/data/google_token.json."
                    )
                }
            return {"error": f"Failed to create calendar event: {err_str}"}

    def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        location: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an existing event on Google Calendar by ID."""
        service = self._get_service()
        if not service:
            return {"error": "Google Calendar is not authenticated."}

        patch_body: Dict[str, Any] = {}
        if summary is not None:
            patch_body["summary"] = summary
        if location is not None:
            patch_body["location"] = location
        if description is not None:
            patch_body["description"] = description
        if start_time is not None:
            if "T" in start_time:
                patch_body["start"] = {"dateTime": start_time if start_time.endswith("Z") or "+" in start_time else start_time + "Z"}
            else:
                patch_body["start"] = {"date": start_time}
        if end_time is not None:
            if "T" in end_time:
                patch_body["end"] = {"dateTime": end_time if end_time.endswith("Z") or "+" in end_time else end_time + "Z"}
            else:
                patch_body["end"] = {"date": end_time}

        if not patch_body:
            return {"error": "No update fields provided."}

        try:
            updated_event = service.events().patch(
                calendarId="primary",
                eventId=event_id,
                body=patch_body
            ).execute()
            self._invalidate_cache()
            return {
                "id": updated_event.get("id"),
                "summary": updated_event.get("summary"),
                "start": updated_event.get("start", {}).get("dateTime", updated_event.get("start", {}).get("date")),
                "end": updated_event.get("end", {}).get("dateTime", updated_event.get("end", {}).get("date")),
                "location": updated_event.get("location", ""),
                "description": updated_event.get("description", "")
            }
        except Exception as e:
            return {"error": f"Failed to update calendar event: {str(e)}"}

    def delete_event(self, event_id: str) -> bool:
        """Delete an event from Google Calendar by ID."""
        service = self._get_service()
        if not service:
            return False

        try:
            service.events().delete(
                calendarId="primary",
                eventId=event_id
            ).execute()
            self._invalidate_cache()
            return True
        except Exception:
            return False

    def search_events(
        self,
        query: str,
        max_results: int = 10,
        time_min: Optional[str] = None,
        time_max: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search calendar events matching text query."""
        service = self._get_service()
        if not service:
            return []

        try:
            params: Dict[str, Any] = {
                "calendarId": "primary",
                "q": query,
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": "startTime"
            }
            if time_min:
                params["timeMin"] = time_min if time_min.endswith("Z") else time_min + "Z"
            if time_max:
                params["timeMax"] = time_max if time_max.endswith("Z") else time_max + "Z"

            events_result = service.events().list(**params).execute()
            items = events_result.get("items", [])
            events = []
            for item in items:
                start = item.get("start", {})
                end = item.get("end", {})
                events.append({
                    "id": item.get("id"),
                    "summary": item.get("summary", "Untitled Event"),
                    "start": start.get("dateTime", start.get("date")),
                    "end": end.get("dateTime", end.get("date")),
                    "location": item.get("location", ""),
                    "description": item.get("description", "")
                })
            return events
        except Exception:
            return []

    def format_calendar_command(self, mode: str = "today", query: str = "") -> str:
        """Format output for /calendar today, /calendar tomorrow, /calendar next, or /calendar search <query>."""
        if not self.auth_manager.is_authenticated():
            return "Google Calendar is not authenticated. Please run Google OAuth setup or place credentials.json in workspace."

        if mode == "search":
            if not query:
                return "Please specify a search query, e.g. /calendar search meeting."
            events = self.search_events(query=query)
            if not events:
                return f"No events found matching '{query}', sir."
            lines = [f"=== Search Results for '{query}' ==="]
            for idx, evt in enumerate(events, 1):
                loc = f" — {evt['location']}" if evt.get("location") else ""
                lines.append(f"{idx}. [{evt['start']}] {evt['summary']}{loc}")
            return "\n".join(lines)

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

