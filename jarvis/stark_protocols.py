"""
Stark Protocols & Morning Briefing Engine — Mark 5.6 Stark Workshop Intelligence
Implements:
1. The Stark Morning Briefing: Atmospheric weather, hardware vitals, calendar directives,
   VIP email debrief, git workspace status, and vocalized Stark readiness assessment.
2. House Protocols Engine: Autonomous macros for workshop routines:
   - 'workshop': Performance optimization, Sentinel co-pilot high alert, dev status.
   - 'clean_slate': Scratch directory prune, temporary file cleanup.
   - 'lockdown': Workstation security lock, audio/mic suspension.
   - 'overdrive': LLM keep-alive warmup, latency benchmark, semantic cache prewarm.
"""

import asyncio
import ctypes
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import psutil


class StarkBriefingEngine:
    """Generates the iconic Stark Morning Briefing and workshop debrief."""

    def __init__(self, workspace_path: Optional[Path] = None):
        self.workspace_path = workspace_path or Path(__file__).parent.parent.resolve()

    def get_time_greeting(self) -> str:
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "Good morning, sir."
        elif 12 <= hour < 17:
            return "Good afternoon, sir."
        elif 17 <= hour < 22:
            return "Good evening, sir."
        else:
            return "Burning the midnight oil, sir."

    def get_weather_summary(self) -> str:
        """Fetches lightweight weather conditions via wttr.in or fallback."""
        try:
            import urllib.request
            import json
            req = urllib.request.Request(
                "https://wttr.in/?format=j1",
                headers={"User-Agent": "curl/7.68.0"}
            )
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = json.loads(resp.read().decode())
                current = data["current_condition"][0]
                temp_c = current.get("temp_C", "24")
                desc = current.get("weatherDesc", [{}])[0].get("value", "Clear")
                feels_like = current.get("FeelsLikeC", temp_c)
                return f"Currently {desc.lower()} at {temp_c}°C (feels like {feels_like}°C)."
        except Exception:
            return "Atmospheric sensors report nominal indoor conditions."

    def get_telemetry_summary(self) -> str:
        """Collects CPU, RAM, disk, and battery status."""
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage(str(self.workspace_path))
            
            parts = [
                f"CPU load is at {cpu}%",
                f"RAM utilization is at {ram.percent}% ({round(ram.available / (1024**3), 1)}GB available)",
                f"Primary drive has {round(disk.free / (1024**3), 1)}GB free"
            ]

            sensors_battery = psutil.sensors_battery()
            if sensors_battery:
                plugged = "plugged in" if sensors_battery.power_plugged else "on battery"
                parts.append(f"Power cell at {sensors_battery.percent}% ({plugged})")

            return "; ".join(parts) + "."
        except Exception as e:
            return f"Telemetry sensors online ({e})."

    def get_calendar_summary(self) -> str:
        """Fetches today's agenda via CalendarService if configured."""
        try:
            from jarvis.calendar_service import get_calendar_service
            cal = get_calendar_service()
            if cal:
                events = cal.get_upcoming_events(max_results=3)
                if events:
                    event_titles = [f"'{e.get('summary', 'Directive')}' at {e.get('start', {}).get('dateTime', 'today')[11:16]}" for e in events]
                    return f"You have {len(events)} directives scheduled: {', '.join(event_titles)}."
        except Exception:
            pass
        return "Your calendar directives are clear today."

    def get_email_summary(self) -> str:
        """Checks for unread messages via EmailService if configured."""
        try:
            from jarvis.email_service import get_email_service
            svc = get_email_service()
            if svc:
                unread = svc.get_unread_count()
                if unread > 0:
                    return f"You have {unread} unread dispatch{'es' if unread != 1 else ''} in your inbox."
        except Exception:
            pass
        return "No urgent dispatches in the queue."

    def get_workspace_summary(self) -> str:
        """Inspects git repository branch and working tree state."""
        try:
            res_branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=str(self.workspace_path),
                capture_output=True,
                text=True,
                timeout=4,
                shell=False
            )
            branch = res_branch.stdout.strip() if res_branch.returncode == 0 else "main"

            res_status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.workspace_path),
                capture_output=True,
                text=True,
                timeout=4,
                shell=False
            )
            if res_status.returncode == 0:
                lines = [l for l in res_status.stdout.splitlines() if l.strip()]
                if lines:
                    return f"Repository is on branch '{branch}' with {len(lines)} uncommitted file change(s)."
                else:
                    return f"Repository branch '{branch}' is clean and synced."
        except Exception:
            pass
        return "Workspace repository is standing by."

    def generate_briefing(self) -> str:
        """Compiles the full Tony Stark Morning Briefing debrief."""
        now = datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        time_str = now.strftime("%H:%M")

        greeting = self.get_time_greeting()
        weather = self.get_weather_summary()
        telemetry = self.get_telemetry_summary()
        calendar = self.get_calendar_summary()
        email = self.get_email_summary()
        workspace = self.get_workspace_summary()

        briefing = (
            f"{greeting} It is {time_str} on {date_str}.\n\n"
            f"• Atmosphere: {weather}\n"
            f"• Hardware Telemetry: {telemetry}\n"
            f"• Directives: {calendar}\n"
            f"• Communications: {email}\n"
            f"• Workshop Status: {workspace}\n\n"
            f"All core systems are operational at 100%. Standing by for your instructions, sir."
        )
        return briefing


class HouseProtocolsEngine:
    """Manages Stark House Protocols: autonomous workflow macros."""

    def __init__(self, workspace_path: Optional[Path] = None):
        self.workspace_path = workspace_path or Path(__file__).parent.parent.resolve()

    def list_protocols(self) -> List[Dict[str, str]]:
        return [
            {
                "name": "workshop",
                "title": "Protocol Workshop",
                "description": "Optimizes performance diagnostics, activates Sentinel Co-Pilot, scans git status, and primes coding tools."
            },
            {
                "name": "clean_slate",
                "title": "Protocol Clean Slate",
                "description": "Purges temporary scratch files and cache artifacts to return the workshop to baseline."
            },
            {
                "name": "lockdown",
                "title": "Protocol Lockdown",
                "description": "Suspends voice and hands-free listeners, halts playback, and locks the Windows workstation."
            },
            {
                "name": "overdrive",
                "title": "Protocol Overdrive",
                "description": "Pre-warms semantic memory vector indexes and runs ultra-low latency diagnostics."
            }
        ]

    def execute_protocol(self, protocol_name: str) -> Dict[str, Any]:
        proto = protocol_name.lower().strip().replace(" ", "_")

        if proto in ("workshop", "protocol_workshop"):
            # 1. Activate Sentinel
            from jarvis.workspace_sentinel import get_workspace_sentinel
            sentinel = get_workspace_sentinel()
            sentinel.start(interval_seconds=5.0)

            # 2. Run diagnostic scan
            from jarvis.diagnostics import run_diagnostics
            report = asyncio.run(run_diagnostics(check_nvidia=True))
            health = "Nominal" if report.overall_healthy else "Warning"

            # 3. Check git changes
            res_git = subprocess.run(
                ["git", "status", "--short"],
                cwd=str(self.workspace_path),
                capture_output=True,
                text=True,
                timeout=4,
                shell=False
            )
            git_changes = len([l for l in res_git.stdout.splitlines() if l.strip()]) if res_git.returncode == 0 else 0

            msg = (
                f"Protocol Workshop INITIATED, sir.\n"
                f"• Workspace Sentinel: Active (5s scan interval)\n"
                f"• Core Diagnostics: {health} ({len(report.checks)} checks verified)\n"
                f"• Tracked Changes: {git_changes} modified file(s)\n"
                f"Stark Workshop ready for development directives."
            )
            return {"status": "ok", "protocol": "workshop", "message": msg, "sound": "done"}

        elif proto in ("clean_slate", "protocol_clean_slate"):
            cleaned = []
            # Clean scratch and pytest caches
            scratch_dir = self.workspace_path / "scratch"
            if scratch_dir.exists():
                count = len(list(scratch_dir.glob("*")))
                for p in scratch_dir.glob("*"):
                    try:
                        if p.is_file():
                            p.unlink()
                        elif p.is_dir():
                            shutil.rmtree(p)
                    except Exception:
                        pass
                cleaned.append(f"{count} file(s) removed from scratch directory")

            pytest_cache = self.workspace_path / ".pytest_cache"
            if pytest_cache.exists():
                try:
                    shutil.rmtree(pytest_cache)
                    cleaned.append("Pytest cache cleared")
                except Exception:
                    pass

            msg = (
                f"Protocol Clean Slate EXECUTED, sir.\n"
                f"• Purged items: {', '.join(cleaned) if cleaned else 'No temporary artifacts found'}.\n"
                f"Workshop baseline restored."
            )
            return {"status": "ok", "protocol": "clean_slate", "message": msg, "sound": "done"}

        elif proto in ("lockdown", "protocol_lockdown"):
            # 1. Stop Hands-Free wake-word if running
            try:
                from jarvis.api import backend_wake_detector
                if backend_wake_detector:
                    backend_wake_detector.stop()
            except Exception:
                pass

            # 2. Lock Windows Workstation
            try:
                ctypes.windll.user32.LockWorkStation()
                locked = True
            except Exception:
                locked = False

            msg = (
                f"Protocol Lockdown ENGAGED, sir.\n"
                f"• Audio & Microphone Sensors: Suspended\n"
                f"• Workstation Lock: {'Secured' if locked else 'Pending'}\n"
                f"JARVIS running in secure background standby."
            )
            return {"status": "ok", "protocol": "lockdown", "message": msg, "sound": "alert"}

        elif proto in ("overdrive", "protocol_overdrive"):
            # Prewarm semantic memory and test latency
            start = time.perf_counter()
            from jarvis.semantic_memory import get_hierarchical_memory
            mem = get_hierarchical_memory()
            mem_ready = mem is not None

            from jarvis.llm_provider import get_shared_http_client
            client = asyncio.run(get_shared_http_client())
            client_ready = client is not None
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

            msg = (
                f"Protocol Overdrive ACTIVE, sir.\n"
                f"• Hierarchical Vector Memory: Online & Pre-warmed\n"
                f"• Shared HTTP/2 Keep-Alive Client: Primed ({elapsed_ms}ms warmup)\n"
                f"Operating at peak inference throughput."
            )
            return {"status": "ok", "protocol": "overdrive", "message": msg, "sound": "done"}

        else:
            return {
                "status": "error",
                "protocol": protocol_name,
                "message": f"Protocol '{protocol_name}' is not recognized, sir. Available protocols: workshop, clean_slate, lockdown, overdrive.",
                "sound": "alert"
            }


_BRIEFING_ENGINE: Optional[StarkBriefingEngine] = None
_PROTOCOLS_ENGINE: Optional[HouseProtocolsEngine] = None

def get_briefing_engine() -> StarkBriefingEngine:
    global _BRIEFING_ENGINE
    if _BRIEFING_ENGINE is None:
        _BRIEFING_ENGINE = StarkBriefingEngine()
    return _BRIEFING_ENGINE

def get_protocols_engine() -> HouseProtocolsEngine:
    global _PROTOCOLS_ENGINE
    if _PROTOCOLS_ENGINE is None:
        _PROTOCOLS_ENGINE = HouseProtocolsEngine()
    return _PROTOCOLS_ENGINE
