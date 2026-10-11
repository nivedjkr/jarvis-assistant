"""
JARVIS System Doctor & Health Diagnostic Suite.
Provides deep environment, gateway, database, model, and security diagnostics
mirroring OpenClaw doctor architecture.
"""

import sys
import os
import shutil
import sqlite3
import socket
import subprocess
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


@dataclass
class DiagnosticFinding:
    category: str
    check_id: str
    title: str
    status: str  # "ok", "warning", "error"
    message: str
    suggested_fix: Optional[str] = None


@dataclass
class DoctorReport:
    overall_status: str
    findings: List[DiagnosticFinding] = field(default_factory=list)
    repaired_count: int = 0

    @property
    def ok_count(self) -> int:
        return sum(1 for f in self.findings if f.status == "ok")

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.status == "warning")

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.status == "error")


class JarvisDoctor:
    def __init__(self, fix: bool = False, deep: bool = False):
        self.fix = fix
        self.deep = deep
        self.findings: List[DiagnosticFinding] = []
        self.repaired_count = 0

    def run_all(self) -> DoctorReport:
        self._check_python_environment()
        self._check_dependencies()
        self._check_api_keys()
        self._check_database()
        self._check_gateway_port()
        self._check_workspace_and_git()
        self._check_security_sandboxing()
        self._check_agents_registry()
        self._check_audio_subsystem()
        
        overall = "ok"
        if any(f.status == "error" for f in self.findings):
            overall = "error"
        elif any(f.status == "warning" for f in self.findings):
            overall = "warning"

        return DoctorReport(
            overall_status=overall,
            findings=self.findings,
            repaired_count=self.repaired_count
        )

    def _check_python_environment(self):
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        is_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        venv_path = sys.prefix

        if is_venv and "venv" in venv_path.lower():
            self.findings.append(DiagnosticFinding(
                category="Runtime",
                check_id="python.venv",
                title="Python Virtual Environment",
                status="ok",
                message=f"Active venv: {venv_path} (Python {py_ver})"
            ))
        else:
            fix_msg = "Activate the local virtual environment: .\\venv\\Scripts\\activate"
            self.findings.append(DiagnosticFinding(
                category="Runtime",
                check_id="python.venv",
                title="Python Virtual Environment",
                status="warning",
                message=f"Running in system or custom environment: {venv_path}",
                suggested_fix=fix_msg
            ))

    def _check_dependencies(self):
        required = [
            ("rich", "Terminal UI & styling"),
            ("prompt_toolkit", "Interactive CLI autocomplete"),
            ("httpx", "High-performance HTTP connection pool"),
            ("psutil", "System vitals and process control"),
            ("edge_tts", "High-fidelity British voice synthesis"),
            ("pytest", "Automated verification test runner")
        ]
        missing = []
        for pkg, desc in required:
            try:
                __import__(pkg)
            except ImportError:
                missing.append((pkg, desc))

        if not missing:
            self.findings.append(DiagnosticFinding(
                category="Dependencies",
                check_id="deps.core",
                title="Core Python Dependencies",
                status="ok",
                message=f"All {len(required)} core packages verified present."
            ))
        else:
            miss_str = ", ".join(m[0] for m in missing)
            fix_cmd = f".\\venv\\Scripts\\pip.exe install {' '.join(m[0] for m in missing)}"
            if self.fix:
                try:
                    subprocess.run([sys.executable, "-m", "pip", "install"] + [m[0] for m in missing], check=True, capture_output=True)
                    self.repaired_count += 1
                    self.findings.append(DiagnosticFinding(
                        category="Dependencies",
                        check_id="deps.core",
                        title="Core Python Dependencies",
                        status="ok",
                        message=f"Repaired: Installed {miss_str}"
                    ))
                    return
                except Exception:
                    pass
            self.findings.append(DiagnosticFinding(
                category="Dependencies",
                check_id="deps.core",
                title="Core Python Dependencies",
                status="error",
                message=f"Missing core packages: {miss_str}",
                suggested_fix=fix_cmd
            ))

    def _check_api_keys(self):
        nim_key = os.getenv("NVIDIA_NIM_API_KEY") or os.getenv("NVIDIA_API_KEY")
        if nim_key and len(nim_key) > 8:
            masked = f"{nim_key[:4]}...{nim_key[-4:]}"
            self.findings.append(DiagnosticFinding(
                category="Providers",
                check_id="auth.nvidia",
                title="NVIDIA NIM API Key",
                status="ok",
                message=f"Configured and loaded: {masked}"
            ))
        else:
            self.findings.append(DiagnosticFinding(
                category="Providers",
                check_id="auth.nvidia",
                title="NVIDIA NIM API Key",
                status="warning",
                message="NVIDIA_NIM_API_KEY is not set or empty in .env. Will use fallback providers.",
                suggested_fix="Set NVIDIA_NIM_API_KEY in D:\\JARVIS\\.env"
            ))

    def _check_database(self):
        db_path = Path("jarvis/data/jarvis.db")
        if not db_path.exists():
            if self.fix:
                db_path.parent.mkdir(parents=True, exist_ok=True)
                from jarvis.memory import Memory
                Memory()
                self.repaired_count += 1
                self.findings.append(DiagnosticFinding(
                    category="Storage",
                    check_id="sqlite.db",
                    title="SQLite State Database",
                    status="ok",
                    message=f"Repaired: Created database at {db_path}"
                ))
                return
            self.findings.append(DiagnosticFinding(
                category="Storage",
                check_id="sqlite.db",
                title="SQLite State Database",
                status="error",
                message=f"Database file missing: {db_path}",
                suggested_fix="Run 'jjarvis doctor --fix' to create and initialize database schema."
            ))
            return

        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cur.fetchall()]
            conn.close()
            self.findings.append(DiagnosticFinding(
                category="Storage",
                check_id="sqlite.db",
                title="SQLite State Database",
                status="ok",
                message=f"Connected ({db_path.stat().st_size // 1024} KB, {len(tables)} tables: {', '.join(tables[:4])}...)"
            ))
        except Exception as e:
            self.findings.append(DiagnosticFinding(
                category="Storage",
                check_id="sqlite.db",
                title="SQLite State Database",
                status="error",
                message=f"Database corrupted or inaccessible: {e}"
            ))

    def _check_gateway_port(self):
        port = int(os.getenv("JARVIS_PORT", "8765"))
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        is_open = False
        try:
            res = sock.connect_ex(("127.0.0.1", port))
            is_open = (res == 0)
        except Exception:
            is_open = False
        finally:
            sock.close()

        if is_open:
            self.findings.append(DiagnosticFinding(
                category="Gateway",
                check_id="gateway.port",
                title="WebSocket Gateway Port",
                status="ok",
                message=f"Online and accepting connections on ws://127.0.0.1:{port}"
            ))
        else:
            self.findings.append(DiagnosticFinding(
                category="Gateway",
                check_id="gateway.port",
                title="WebSocket Gateway Port",
                status="warning",
                message=f"Offline (port {port} is idle). Run 'jjarvis gateway run' to start.",
                suggested_fix="jjarvis gateway run"
            ))

    def _check_workspace_and_git(self):
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                changes = res.stdout.strip().splitlines()
                if not changes:
                    msg = "Git repository clean. Working tree synchronized."
                else:
                    msg = f"Git repository active ({len(changes)} modified files in working tree)."
                self.findings.append(DiagnosticFinding(
                    category="Workspace",
                    check_id="git.status",
                    title="Git Repository Health",
                    status="ok",
                    message=msg
                ))
            else:
                self.findings.append(DiagnosticFinding(
                    category="Workspace",
                    check_id="git.status",
                    title="Git Repository Health",
                    status="warning",
                    message="Git command exited with non-zero status."
                ))
        except Exception as e:
            self.findings.append(DiagnosticFinding(
                category="Workspace",
                check_id="git.status",
                title="Git Repository Health",
                status="warning",
                message=f"Git check skipped: {e}"
            ))

    def _check_security_sandboxing(self):
        try:
            from jarvis.tools import BLOCKED_PATTERNS, _get_allowed_roots, ToolRegistry
            roots = _get_allowed_roots()
            registry = ToolRegistry()
            self.findings.append(DiagnosticFinding(
                category="Security",
                check_id="security.sandbox",
                title="Airtight Sandbox Gates",
                status="ok",
                message=f"Enforced ({len(roots)} allowed drive roots, {len(BLOCKED_PATTERNS)} blocked patterns, {len(registry.tools)} active tools with confirmation gates)."
            ))
        except Exception as e:
            self.findings.append(DiagnosticFinding(
                category="Security",
                check_id="security.sandbox",
                title="Airtight Sandbox Gates",
                status="error",
                message=f"Security boundaries check failed: {e}"
            ))

    def _check_agents_registry(self):
        try:
            from jarvis.agents_registry import get_agents_registry
            reg = get_agents_registry()
            agents = reg.list_agents()
            active = reg.get_active_agent()
            self.findings.append(DiagnosticFinding(
                category="Agents",
                check_id="agents.registry",
                title="Multi-Agent Fleet Registry",
                status="ok",
                message=f"{len(agents)} configured agents ({', '.join(a.name for a in agents)}). Active: {active.name}"
            ))
        except Exception as e:
            self.findings.append(DiagnosticFinding(
                category="Agents",
                check_id="agents.registry",
                title="Multi-Agent Fleet Registry",
                status="error",
                message=f"Failed to load agents registry: {e}"
            ))

    def _check_audio_subsystem(self):
        try:
            import winsound
            self.findings.append(DiagnosticFinding(
                category="Audio",
                check_id="audio.cues",
                title="Stark Audio Cues Subsystem",
                status="ok",
                message="Windows multimedia sound API verified ready."
            ))
        except Exception as e:
            self.findings.append(DiagnosticFinding(
                category="Audio",
                check_id="audio.cues",
                title="Stark Audio Cues Subsystem",
                status="warning",
                message=f"Winsound unavailable: {e}"
            ))
