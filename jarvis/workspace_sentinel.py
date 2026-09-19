"""
WorkspaceSentinel — Mark 5.4 Cross-Modal Streaming Perception Pipeline
Monitors real-time desktop window changes, workspace modifications, diagnostic alerts,
and system state in a non-blocking background loop, feeding anticipatory perception
into the Proactive Engine and WebSocket clients.
"""

import asyncio
import collections
import ctypes
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable


@dataclass
class PerceptualEvent:
    id: str
    event_type: str  # "WINDOW_FOCUS" | "GIT_CHANGE" | "DIAGNOSTIC_ALERT" | "SCREEN_STATE"
    summary: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "details": self.details
        }


class WorkspaceSentinel:
    """
    Continuous background perceptual sentinel.
    Tracks active desktop focus, workspace file changes, and diagnostic health.
    """

    def __init__(self, workspace_path: Optional[str] = None, max_events: int = 100):
        self.workspace_path = Path(workspace_path) if workspace_path else Path(__file__).parent.parent.resolve()
        self.events_buffer: collections.deque = collections.deque(maxlen=max_events)
        self.running: bool = False
        self.interval_seconds: float = 10.0
        
        self.last_window_title: str = ""
        self.last_git_status: str = ""
        self.co_pilot_enabled: bool = True
        self.last_reported_anomalies: set = set()
        self.callbacks: List[Callable[[PerceptualEvent], Any]] = []
        
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def add_callback(self, callback: Callable[[PerceptualEvent], Any]):
        """Registers a listener callback for perceptual events."""
        with self._lock:
            if callback not in self.callbacks:
                self.callbacks.append(callback)

    def remove_callback(self, callback: Callable[[PerceptualEvent], Any]):
        """Unregisters a listener callback."""
        with self._lock:
            if callback in self.callbacks:
                self.callbacks.remove(callback)

    def get_active_window_title(self) -> str:
        """Retrieves foreground window title via native Windows API."""
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return ""
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return ""
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value.strip()
        except Exception:
            return ""

    def check_git_status(self) -> Optional[str]:
        """Runs git status --porcelain to detect active workspace file edits."""
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.workspace_path),
                capture_output=True,
                text=True,
                timeout=5,
                shell=False
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
    def scan_for_code_anomalies(self) -> List[PerceptualEvent]:
        """Inspects modified Python files in the workspace for syntax errors or merge conflicts."""
        anomalies = []
        import ast
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.workspace_path),
                capture_output=True,
                text=True,
                timeout=4,
                shell=False
            )
            if res.returncode != 0:
                return anomalies
            
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split(maxsplit=1)
                if len(parts) < 2:
                    continue
                file_rel = parts[1].strip()
                if not file_rel.endswith(".py"):
                    continue
                file_path = self.workspace_path / file_rel
                if not file_path.exists() or not file_path.is_file():
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()

                    # 1. Check for merge conflicts
                    if "<<<<<<< HEAD" in content and "=======" in content:
                        anomaly_key = f"conflict_{file_rel}"
                        if anomaly_key not in self.last_reported_anomalies:
                            self.last_reported_anomalies.add(anomaly_key)
                            anomalies.append(PerceptualEvent(
                                id=f"evt_{uuid.uuid4().hex[:8]}",
                                event_type="CODE_ANOMALY",
                                summary=f"Merge conflict detected in '{file_rel}'",
                                details={"file": file_rel, "anomaly_type": "MERGE_CONFLICT"}
                            ))

                    # 2. Check for syntax error
                    try:
                        ast.parse(content, filename=file_rel)
                    except SyntaxError as syn_err:
                        anomaly_key = f"syntax_{file_rel}_{syn_err.lineno}"
                        if anomaly_key not in self.last_reported_anomalies:
                            self.last_reported_anomalies.add(anomaly_key)
                            anomalies.append(PerceptualEvent(
                                id=f"evt_{uuid.uuid4().hex[:8]}",
                                event_type="CODE_ANOMALY",
                                summary=f"Syntax error in '{file_rel}' at line {syn_err.lineno}: {syn_err.msg}",
                                details={
                                    "file": file_rel,
                                    "line": syn_err.lineno,
                                    "msg": syn_err.msg,
                                    "anomaly_type": "SYNTAX_ERROR"
                                }
                            ))
                except Exception:
                    pass
        except Exception:
            pass
        return anomalies

    def scan_once(self) -> List[PerceptualEvent]:
        """
        Executes a single observation pass across desktop, filesystem, and vitals.
        Returns newly generated events.
        """
        new_events = []

        # 1. Desktop Window Focus Check
        current_window = self.get_active_window_title()
        if current_window and current_window != self.last_window_title:
            evt = PerceptualEvent(
                id=f"evt_{uuid.uuid4().hex[:8]}",
                event_type="WINDOW_FOCUS",
                summary=f"Desktop focus switched to '{current_window}'",
                details={
                    "previous_window": self.last_window_title,
                    "active_window": current_window
                }
            )
            self.last_window_title = current_window
            new_events.append(evt)

        # 2. Workspace Git Changes Check
        current_git = self.check_git_status()
        if current_git is not None and current_git != self.last_git_status:
            # Analyze diff summary
            lines = [line.strip() for line in current_git.splitlines() if line.strip()]
            mod_count = len(lines)
            if mod_count > 0:
                evt = PerceptualEvent(
                    id=f"evt_{uuid.uuid4().hex[:8]}",
                    event_type="GIT_CHANGE",
                    summary=f"Workspace has {mod_count} modified/untracked file(s)",
                    details={
                        "modified_files": lines[:10],
                        "total_changes": mod_count
                    }
                )
                new_events.append(evt)
            self.last_git_status = current_git

        # 3. Autonomous Code Anomaly / Co-Pilot Check
        if self.co_pilot_enabled:
            anomaly_events = self.scan_for_code_anomalies()
            new_events.extend(anomaly_events)

        # Record events and dispatch callbacks
        with self._lock:
            for evt in new_events:
                self.events_buffer.append(evt)
                for cb in self.callbacks:
                    try:
                        cb(evt)
                    except Exception as e:
                        print(f"[SENTINEL] Callback error: {e}")

        return new_events

    def _sentinel_loop(self):
        """Worker thread loop polling environment at configured intervals."""
        while not self._stop_event.is_set():
            try:
                self.scan_once()
            except Exception as e:
                print(f"[SENTINEL] Loop exception: {e}")
            self._stop_event.wait(self.interval_seconds)

    def start(self, interval_seconds: float = 10.0) -> bool:
        """Starts the non-blocking background sentinel."""
        if self.running:
            return True
        self.interval_seconds = interval_seconds
        self._stop_event.clear()
        self.running = True
        self._thread = threading.Thread(target=self._sentinel_loop, daemon=True, name="WorkspaceSentinelThread")
        self._thread.start()
        print(f"[SENTINEL] Background sentinel started (interval: {self.interval_seconds}s).")
        return True

    def stop(self) -> bool:
        """Stops the background sentinel."""
        if not self.running:
            return False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self.running = False
        print("[SENTINEL] Background sentinel stopped.")
        return True

    def toggle_copilot(self, enabled: bool) -> bool:
        """Toggles Sentinel Co-Pilot real-time code anomaly detection."""
        self.co_pilot_enabled = enabled
        return self.co_pilot_enabled

    def get_status(self) -> Dict[str, Any]:
        """Returns runtime status and event counts."""
        return {
            "running": self.running,
            "interval_seconds": self.interval_seconds,
            "co_pilot_enabled": self.co_pilot_enabled,
            "buffered_events_count": len(self.events_buffer),
            "last_active_window": self.last_window_title,
            "workspace_path": str(self.workspace_path)
        }

    def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns the most recent perceptual events."""
        with self._lock:
            events = list(self.events_buffer)
        return [evt.to_dict() for evt in reversed(events[-limit:])]


_SENTINEL_INSTANCE: Optional[WorkspaceSentinel] = None

def get_workspace_sentinel() -> WorkspaceSentinel:
    global _SENTINEL_INSTANCE
    if _SENTINEL_INSTANCE is None:
        _SENTINEL_INSTANCE = WorkspaceSentinel()
    return _SENTINEL_INSTANCE
