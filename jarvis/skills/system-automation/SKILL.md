---
name: system-automation
description: OS process monitoring, shell command execution, file system management, vitals diagnostics, and background task scheduling. Activate when interacting with the host operating system.
category: system
---

# System Automation & Process Management

Enables safe and reliable interaction with the host operating system (Windows/Linux) while adhering to security rules.

## Core Capabilities

1. **Shell Command Execution (`run_command`)**:
   - Execute CLI commands, inspect outputs, and check return codes.
   - Strictly avoid shell injection (`shell=False` with list args internally).
   - Sensitive or dangerous commands trigger the safety confirmation gate.
2. **Process Management**:
   - Inspect active running processes, CPU, RAM, and disk utilization via `get_system_status` and `get_disk_usage`.
   - Safely launch desktop applications (`open_application`) or terminate them (`close_application`).
3. **Task Scheduling (`schedule_task`)**:
   - Set one-shot timers or recurring cron triggers for asynchronous alerts and follow-ups.
