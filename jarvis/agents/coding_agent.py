"""
CodingAgent for JARVIS Mk4
Specialized agent role for software engineering and debugging.
Strictly respects the verified debug-loop rules in AGENTS.md.
"""

from typing import Optional, Set
from jarvis.agents.base_agent import BaseAgent

CODING_TOOLS: Set[str] = {
    "read_file",
    "write_file",
    "list_files",
    "search_files",
    "find_in_file",
    "append_to_file",
    "inspect_project",
    "run_tests",
    "run_project",
    "dependency_scan",
    "secret_scan",
    "run_command",
    "git_status",
    "git_diff",
    "git_log",
    "git_add_commit_push",
    "git_create_branch",
    "git_switch_branch",
    "git_pull",
    "gh_list_repos",
    "gh_list_issues",
    "gh_create_issue",
    "gh_close_issue",
    "gh_comment_issue",
    "gh_list_prs",
    "gh_create_pr",
    "gh_merge_pr",
    "gh_ci_status",
}


class CodingAgent(BaseAgent):
    """Logical agent role for coding tasks following the verified debug loop."""

    def __init__(self, allowed_tools: Optional[Set[str]] = None):
        tools = allowed_tools if allowed_tools is not None else CODING_TOOLS
        system_prompt = (
            "You are the JARVIS Coding Agent.\n"
            "You handle software development and debugging following the verified debug loop:\n"
            "1. inspect_project first to understand directory structure and test runners.\n"
            "2. run_tests to observe baseline pass/fail status and tracebacks.\n"
            "3. Apply targeted code modifications.\n"
            "4. re-run run_tests to verify if the fix succeeded.\n"
            "5. Never claim a fix is complete without running tests to verify.\n"
            "Always respect ALLOWED_ROOTS and security bounds."
        )
        super().__init__(
            name="CodingAgent",
            role_description="Software development, code editing, testing, and debugging.",
            system_prompt=system_prompt,
            allowed_tools=tools
        )
