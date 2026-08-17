import subprocess
import sqlite3
import os
import time

from pathlib import Path
from typing import Dict, Any, List

class HealthChecker:
    def __init__(self):
        self.results: Dict[str, Dict[str, Any]] = {}
        self.critical_failures: List[str] = []

    async def run_all(self) -> dict:
        checks = [
            ("Database",      self.check_database),
            ("NVIDIA NIM API", self.check_nvidia_api),
            ("GitHub CLI",    self.check_github),
            ("Voice TTS",     self.check_tts),
            ("Microphone",    self.check_microphone),
            ("Internet",      self.check_internet),
            ("Disk Space",    self.check_disk_space),
            ("Config File",   self.check_config),
        ]
        
        import asyncio
        tasks = [
            self._run_check(name, check) 
            for name, check in checks
        ]
        await asyncio.gather(*tasks)
        return self.results

    async def _run_check(self, name, check_fn):
        try:
            t0 = time.time()
            result = await check_fn()
            duration = time.time() - t0
            self.results[name] = {
                "status": "ok",
                "detail": result,
                "duration": f"{duration:.2f}s"
            }
        except Exception as e:
            self.results[name] = {
                "status": "fail",
                "detail": str(e)[:100],
                "duration": "—"
            }
            if name in ["Database", "NVIDIA NIM API"]:
                self.critical_failures.append(name)

    async def check_database(self) -> str:
        db_path = Path('jarvis/data/jarvis.db')
        if not db_path.exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(db_path))
            conn.execute("CREATE TABLE IF NOT EXISTS facts (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, content TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            conn.commit()
            conn.close()
            return "Connected — 0 facts stored (new DB created)"

        conn = sqlite3.connect(str(db_path))
        try:
            count = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        except Exception:
            count = 0
        conn.close()
        return f"Connected — {count} facts stored"

    async def check_nvidia_api(self) -> str:
        import httpx
        key = os.getenv("NVIDIA_NIM_API_KEY")
        if not key:
            raise Exception("NVIDIA_NIM_API_KEY not set")
        if key == "your_key_here":
            raise Exception("API key is placeholder")
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://integrate.api.nvidia.com",
                timeout=5.0
            )
        return f"Reachable (HTTP {r.status_code})"

    async def check_github(self) -> str:
        result = subprocess.run(
            ['gh', 'auth', 'status'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            raise Exception("gh CLI not authenticated")
        for line in (result.stderr + "\n" + result.stdout).split('\n'):
            if 'Logged in' in line:
                return line.strip()
        return "Authenticated"

    async def check_tts(self) -> str:
        try:
            import edge_tts
            return "edge-tts available"
        except ImportError:
            raise Exception("edge-tts not installed")

    async def check_microphone(self) -> str:
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = [
                d for d in devices 
                if d.get('max_input_channels', 0) > 0
            ]
            if not input_devices:
                raise Exception("No input devices found")
            default = sd.query_devices(kind='input')
            return f"Found: {default.get('name', 'Default Mic')}"
        except Exception as e:
            raise Exception(f"Mic check failed: {e}")

    async def check_internet(self) -> str:
        import httpx
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                r = await client.get("https://1.1.1.1", timeout=3.0)
            return f"Connected (HTTP {r.status_code})"
        except Exception:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                r = await client.get("https://www.google.com", timeout=3.0)
            return "Connected"

    async def check_disk_space(self) -> str:
        import shutil
        drive = "C:\\" if os.name == "nt" else "/"
        usage = shutil.disk_usage(drive)
        free_gb = usage.free / (1024**3)
        if free_gb < 1.0:
            raise Exception(f"Low disk space: {free_gb:.1f}GB free")
        return f"{free_gb:.1f}GB free on {drive}"

    async def check_config(self) -> str:
        if not Path('config.yaml').exists():
            raise Exception("config.yaml not found")
        if not Path('.env').exists():
            raise Exception(".env not found")
        return "config.yaml and .env present"

    def render_results(self) -> str:
        from rich.table import Table
        from rich.console import Console
        from io import StringIO

        table = Table(
            title="JARVIS HEALTH CHECK",
            border_style="cyan"
        )
        table.add_column("System", style="cyan")
        table.add_column("Status")
        table.add_column("Detail")
        table.add_column("Time", justify="right")

        for name, result in self.results.items():
            status = result['status']
            icon = "✓" if status == "ok" else "✗"
            color = "green" if status == "ok" else "red"
            table.add_row(
                name,
                f"[{color}]{icon} {status.upper()}[/]",
                result['detail'],
                result.get('duration', '—')
            )

        buf = StringIO()
        console = Console(file=buf, force_terminal=True)
        console.print(table)
        return buf.getvalue()
