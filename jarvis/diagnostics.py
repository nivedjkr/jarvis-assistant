"""
JARVIS System Diagnostics & Health Check Suite
Provides automated launch diagnostics and status reporting for all core services,
credentials, network connectivity, system ports, and integrations.
"""

import os
import sys
import socket
import shutil
import asyncio
import subprocess
import sqlite3
from typing import List, Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# Ensure root is in sys.path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))
load_dotenv(dotenv_path=root_dir / '.env')


class HealthCheckItem:
    """Represents a single diagnostic check item."""
    def __init__(self, name: str, category: str, critical: bool = True):
        self.name = name
        self.category = category
        self.critical = critical
        self.status: str = "PENDING"  # PASS, WARN, FAIL
        self.message: str = ""
        self.fix_recommendation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "critical": self.critical,
            "status": self.status,
            "message": self.message,
            "fix_recommendation": self.fix_recommendation,
        }


class HealthCheckReport:
    """Aggregates all diagnostic check items and provides summary formatting."""
    def __init__(self):
        self.items: List[HealthCheckItem] = []
        self.overall_status: str = "OK"  # OK, WARN, ERROR
        self.duration_ms: float = 0.0

    def add(self, item: HealthCheckItem):
        self.items.append(item)
        if item.status == "FAIL":
            if item.critical:
                self.overall_status = "ERROR"
            elif self.overall_status != "ERROR":
                self.overall_status = "WARN"
        elif item.status == "WARN" and self.overall_status == "OK":
            self.overall_status = "WARN"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "duration_ms": round(self.duration_ms, 2),
            "items": [item.to_dict() for item in self.items]
        }

    def format_plain(self) -> str:
        """Returns a plain text console summary safely printable on all terminals."""
        lines = []
        lines.append("==================================================")
        lines.append("             JARVIS STARTUP DIAGNOSTICS            ")
        lines.append("==================================================")
        
        for item in self.items:
            symbol = "[PASS]" if item.status == "PASS" else "[WARN]" if item.status == "WARN" else "[FAIL]"
            lines.append(f"{symbol} {item.name}: {item.message}")
            if item.fix_recommendation and item.status != "PASS":
                lines.append(f"   -> FIX: {item.fix_recommendation}")

        lines.append("--------------------------------------------------")
        if self.overall_status == "OK":
            lines.append("STATUS: [PASS] ALL SYSTEMS OPERATIONAL")
        elif self.overall_status == "WARN":
            lines.append("STATUS: [WARN] OPERATIONAL WITH WARNINGS")
        else:
            lines.append("STATUS: [FAIL] SYSTEM CRITICAL FAILURE DETECTED")
        lines.append("==================================================")
        return "\n".join(lines)


def check_port_8765(report: HealthCheckReport) -> HealthCheckItem:
    """Check if WebSocket port 8765 is available or bound."""
    item = HealthCheckItem("WebSocket Server Port 8765", "Network", critical=True)
    port = 8765
    host = "127.0.0.1"

    # Try connecting to port 8765
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.3)
    res = sock.connect_ex((host, port))
    sock.close()

    if res == 0:
        # Something is listening on 8765
        item.status = "WARN"
        item.message = f"Port {port} is currently occupied."
        item.fix_recommendation = (
            "If launching backend, free port 8765 with PowerShell: "
            "Get-NetTCPConnection -LocalPort 8765 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"
        )
    else:
        item.status = "PASS"
        item.message = f"Port {port} is free and ready for binding."
    
    report.add(item)
    return item


async def check_nvidia_api(report: HealthCheckReport) -> HealthCheckItem:
    """Check if NVIDIA NIM API Key is valid and endpoint is reachable."""
    item = HealthCheckItem("NVIDIA NIM LLM Service", "API Credentials", critical=True)
    api_key = os.getenv("NVIDIA_NIM_API_KEY")

    if not api_key or api_key.strip() == "" or "nvapi-your-key-here" in api_key:
        item.status = "FAIL"
        item.message = "NVIDIA_NIM_API_KEY is missing or unconfigured in .env."
        item.fix_recommendation = (
            "Obtain a key from https://build.nvidia.com and add 'NVIDIA_NIM_API_KEY=nvapi-...' to your .env file."
        )
        report.add(item)
        return item

    # Ping NVIDIA API endpoint
    try:
        import httpx
        url = "https://integrate.api.nvidia.com/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers=headers)
            
        if resp.status_code == 200:
            item.status = "PASS"
            item.message = "NVIDIA NIM API key authenticated & endpoint reachable."
        elif resp.status_code in (401, 403):
            item.status = "FAIL"
            item.message = f"NVIDIA API Key invalid or unauthorized (HTTP {resp.status_code})."
            item.fix_recommendation = "Check NVIDIA_NIM_API_KEY in .env. Ensure key has active credits/quota."
        else:
            item.status = "WARN"
            item.message = f"NVIDIA endpoint returned unexpected HTTP status {resp.status_code}."
            item.fix_recommendation = "Check https://build.nvidia.com service status."
    except Exception as e:
        item.status = "FAIL"
        item.message = f"Failed to reach NVIDIA API: {type(e).__name__} ({e})."
        item.fix_recommendation = "Check your internet connection, firewall, or DNS settings."

    report.add(item)
    return item


def check_github_auth(report: HealthCheckReport) -> HealthCheckItem:
    """Check GitHub CLI installation and authentication status."""
    item = HealthCheckItem("GitHub CLI (`gh`) Integration", "Integrations", critical=False)

    if not shutil.which("gh"):
        item.status = "WARN"
        item.message = "GitHub CLI (`gh`) executable not found in PATH."
        item.fix_recommendation = "Install GitHub CLI via 'winget install GitHub.cli' or from cli.github.com."
        report.add(item)
        return item

    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            item.status = "PASS"
            item.message = "GitHub CLI authenticated."
        else:
            item.status = "WARN"
            item.message = "GitHub CLI installed but not authenticated."
            item.fix_recommendation = "Run 'gh auth login' in terminal to log in."
    except Exception as e:
        item.status = "WARN"
        item.message = f"GitHub CLI check error: {e}"
        item.fix_recommendation = "Run 'gh auth status' to inspect authentication."

    report.add(item)
    return item


def check_google_auth(report: HealthCheckReport) -> HealthCheckItem:
    """Check Google OAuth2 setup (Calendar & Gmail)."""
    item = HealthCheckItem("Google Services OAuth", "Integrations", critical=False)
    
    try:
        from jarvis.google_auth import GoogleAuthManager
        manager = GoogleAuthManager()
        creds = manager.get_credentials()
        
        if creds and creds.valid:
            item.status = "PASS"
            item.message = "Google OAuth2 credentials valid."
        elif manager.credentials_path.exists():
            item.status = "WARN"
            item.message = "credentials.json found, but active OAuth token is unauthenticated or expired."
            item.fix_recommendation = "Run Google authorization prompt to log in."
        else:
            item.status = "WARN"
            item.message = "Google credentials.json missing (Optional)."
            item.fix_recommendation = "Place credentials.json in project root if you want Google Calendar/Gmail integration."
    except Exception as e:
        item.status = "WARN"
        item.message = f"Google Auth check error: {e}"

    report.add(item)
    return item


def check_obsidian(report: HealthCheckReport) -> HealthCheckItem:
    """Check Obsidian vault configuration and path."""
    item = HealthCheckItem("Obsidian Vault & Memory", "Integrations", critical=False)
    config_path = root_dir / "config.yaml"
    
    vault_path = None
    if config_path.exists():
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            vault_path = cfg.get("obsidian", {}).get("vault_path")
        except Exception:
            pass

    if vault_path and Path(vault_path).exists():
        item.status = "PASS"
        item.message = f"Obsidian vault verified at '{vault_path}'."
    elif vault_path:
        item.status = "WARN"
        item.message = f"Obsidian vault path '{vault_path}' does not exist."
        item.fix_recommendation = "Update 'obsidian.vault_path' in config.yaml."
    else:
        item.status = "WARN"
        item.message = "Obsidian vault path not set in config.yaml (Optional)."

    report.add(item)
    return item


def check_sqlite_db(report: HealthCheckReport) -> HealthCheckItem:
    """Check SQLite persistent database."""
    item = HealthCheckItem("SQLite Database", "Core Memory", critical=True)
    db_path = root_dir / "jarvis" / "data" / "jarvis.db"

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        item.status = "PASS"
        item.message = f"SQLite database online ({len(tables)} tables present)."
    except Exception as e:
        item.status = "FAIL"
        item.message = f"SQLite database connection error: {e}"
        item.fix_recommendation = "Ensure write permissions for jarvis/data/ directory."

    report.add(item)
    return item


def check_voice_tts(report: HealthCheckReport) -> HealthCheckItem:
    """Check TTS voice engine status."""
    item = HealthCheckItem("Edge-TTS Voice Engine", "Voice", critical=False)

    try:
        import edge_tts
        item.status = "PASS"
        item.message = "edge-tts voice engine package available."
    except ImportError:
        item.status = "WARN"
        item.message = "edge-tts module not installed."
        item.fix_recommendation = "Run 'pip install edge-tts' to enable voice output."

    report.add(item)
    return item


async def run_diagnostics(check_nvidia: bool = True) -> HealthCheckReport:
    """Run full diagnostic test suite asynchronously."""
    import time
    start_time = time.time()
    report = HealthCheckReport()

    # Synchronous checks
    check_port_8765(report)
    check_sqlite_db(report)
    check_github_auth(report)
    check_google_auth(report)
    check_obsidian(report)
    check_voice_tts(report)

    # Async API check
    if check_nvidia:
        await check_nvidia_api(report)

    report.duration_ms = (time.time() - start_time) * 1000
    return report


def run_diagnostics_sync(check_nvidia: bool = True) -> HealthCheckReport:
    """Synchronous helper for calling run_diagnostics."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # In an active event loop, create task or new loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(lambda: asyncio.run(run_diagnostics(check_nvidia))).result()
        else:
            return loop.run_until_complete(run_diagnostics(check_nvidia))
    except RuntimeError:
        return asyncio.run(run_diagnostics(check_nvidia))


if __name__ == "__main__":
    rep = run_diagnostics_sync()
    print(rep.format_plain())
