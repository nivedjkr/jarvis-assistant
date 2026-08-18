"""
SystemAgent for JARVIS Mk4
Specialized agent role for computer, system, app, and filesystem operations.
"""

from typing import Optional, Set
from jarvis.agents.base_agent import BaseAgent

SYSTEM_TOOLS: Set[str] = {
    "get_system_status",
    "open_application",
    "close_application",
    "open_file_with_app",
    "open_url",
    "open_website",
    "list_files",
    "create_directory",
    "delete_file",
    "move_file",
    "copy_file",
    "rename_file",
    "get_file_info",
    "get_disk_usage",
    "copy_to_clipboard",
    "paste_from_clipboard",
    "run_command",
}


class SystemAgent(BaseAgent):
    """Logical agent role for system management and desktop automation."""

    def __init__(self, allowed_tools: Optional[Set[str]] = None):
        tools = allowed_tools if allowed_tools is not None else SYSTEM_TOOLS
        system_prompt = (
            "You are the JARVIS System Agent.\n"
            "You handle computer control, application launch, process management, and local files.\n"
            "All dangerous or destructive actions must pass through the security confirmation gate."
        )
        super().__init__(
            name="SystemAgent",
            role_description="System administration, application control, hardware stats, and filesystem tasks.",
            system_prompt=system_prompt,
            allowed_tools=tools
        )
