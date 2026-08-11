# JARVIS Tool Reference

This document catalogs all registered tool schemas available to JARVIS, organized by category with descriptions and natural language execution triggers.

## Summary Table
| Category | Count | Primary Functions |
|----------|-------|-------------------|
| File Operations | 7 | `read_file`, `write_file`, `list_files`, `delete_file`, `create_directory` |
| Application Control | 3 | `open_application`, `close_application`, `list_running_applications` |
| Browser Navigation | 3 | `open_url`, `open_website`, `search_web` |
| System Telemetry | 2 | `get_system_status`, `run_diagnostics` |
| Clipboard Management | 2 | `copy_to_clipboard`, `get_clipboard` |
| GitHub & Git Workflow | 18 | `git_status`, `git_log`, `git_commit`, `git_push`, `gh_list_repos`, `gh_list_issues`, `gh_create_issue`, `gh_merge_pr`, `gh_ci_status` |
| System Files & Desktop | 7 | `read_system_file`, `write_system_file`, `list_desktop_files` |
| Trading & Velocity | 4 | `get_stock_price`, `log_inventory_event`, `get_inventory_status`, `set_inventory_threshold` |
| Memory & Directives | 4 | `remember_fact`, `search_memory`, `set_reminder`, `list_reminders` |
| Projects & DB | 6 | `list_projects`, `get_project_details`, `get_active_projects_summary` |
| Email & Calendar | 3 | `check_email`, `send_email`, `delete_calendar_event` |

---

## 1. File Operations & System Controls
- `write_file`: Create or overwrite a local file.
  - *Trigger*: "Create a file named notes.txt with hello world"
- `read_file`: Read exact text lines from a file.
  - *Trigger*: "Read main.js"
- `list_files`: List directory contents.
  - *Trigger*: "List all files in src/"
- `create_directory`: Create a new folder directory.
  - *Trigger*: "Make a directory called build"

## 2. GitHub & Developer Workflow
- `gh_list_repos`: Fetch user's public and private repositories.
  - *Trigger*: "Show my github repos"
- `gh_list_issues`: Fetch open/closed issues.
  - *Trigger*: "List open issues on jarvis-assistant"
- `gh_create_issue`: Create a GitHub issue.
  - *Trigger*: "Create an issue titled Bug in UI"
- `gh_merge_pr`: Merge a pull request (requires pending confirmation).
  - *Trigger*: "Merge PR #4"
- `git_status`: Show current repository status.
  - *Trigger*: "Check git status"

## 3. Email & Calendar
- `check_email`: Triage Gmail unread inbox items.
  - *Trigger*: "Check my email"
- `send_email`: Send an email (requires pending confirmation).
  - *Trigger*: "Send email to alex@example.com subject Update body Here is the report"
- `delete_calendar_event`: Delete event from Google Calendar (requires pending confirmation).
  - *Trigger*: "Delete calendar event evt123"

## 4. Diagnostics & System Observability
- `get_system_status`: Inspect live CPU, RAM, Disk, and GPU metrics.
  - *Trigger*: "What is my cpu usage?"
- `run_diagnostics`: Execute multi-check health suite.
  - *Trigger*: "Run system diagnostics"
