"""
CommunicationAgent for JARVIS Mk4
Specialized agent role for email, calendar, notes, and user notifications.
Reuses existing ToolRegistry service instances (Gmail, Calendar, Obsidian).
"""

from typing import Optional, Set
from jarvis.agents.base_agent import BaseAgent

COMMUNICATION_TOOLS: Set[str] = {
    "check_email",
    "read_email",
    "email_summary",
    "list_sent_emails",
    "delete_sent_email",
    "send_email",
    "list_calendar_events",
    "check_calendar",
    "create_calendar_event",
    "search_calendar_events",
    "update_calendar_event",
    "delete_calendar_event",
    "search_obsidian",
    "create_obsidian_note",
    "link_obsidian_notes",
    "append_daily_note",
    "append_obsidian_note",
    "remember_fact",
}


class CommunicationAgent(BaseAgent):
    """Logical agent role for messaging, schedule management, and Obsidian note-taking."""

    def __init__(self, allowed_tools: Optional[Set[str]] = None):
        tools = allowed_tools if allowed_tools is not None else COMMUNICATION_TOOLS
        system_prompt = (
            "You are the JARVIS Communication Agent.\n"
            "You manage email, calendar schedules, and Obsidian note logging.\n"
            "Never send emails without explicit user command or confirmation.\n"
            "All outbound email commands pass through the existing confirmation gate."
        )
        super().__init__(
            name="CommunicationAgent",
            role_description="Email, calendar management, Obsidian notes, and user directives.",
            system_prompt=system_prompt,
            allowed_tools=tools
        )
