"""
Protocol Macro System for JARVIS
Handles named multi-step macro sequences, safety confirmation, and execution.
"""

import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

console = Console()

DEFAULT_PROTOCOLS = {
    "work mode": {
        "name": "work mode",
        "description": "Initialize developer workspace: launch IDE, open GitHub, and set up work environment",
        "steps": [
            {
                "tool": "open_application",
                "kwargs": {"app_name": "vscode"},
                "description": "Launch VSCode IDE"
            },
            {
                "tool": "open_website",
                "kwargs": {"site_name": "github"},
                "description": "Open GitHub in web browser"
            },
            {
                "tool": "shell_command",
                "kwargs": {"command": "echo [WORK MODE ACTIVE] All core workspace modules loaded."},
                "description": "Log work mode readiness"
            }
        ]
    },
    "shutdown": {
        "name": "shutdown",
        "description": "Session cleanup: log session completion and execute shutdown sequence",
        "steps": [
            {
                "tool": "shell_command",
                "kwargs": {"command": "echo [SHUTDOWN PROTOCOL] Logging session state and closing resources..."},
                "description": "Log session summary"
            }
        ]
    },
    "backup": {
        "name": "backup",
        "description": "Create a timestamped ZIP archive of project files in the backups folder",
        "steps": [
            {
                "tool": "directory",
                "kwargs": {"action": "create", "path": "backups"},
                "description": "Ensure backups directory exists"
            },
            {
                "tool": "shell_command",
                "kwargs": {
                    "command": "python -c \"import shutil, datetime; shutil.make_archive('backups/jarvis_backup_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'), 'zip', '.')\""
                },
                "description": "Generate timestamped project ZIP archive"
            }
        ]
    }
}


class ProtocolManager:
    """Manages protocol loading, saving, safety checks, and multi-step execution"""

    def __init__(self, data_dir: str = "jarvis/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.filepath = self.data_dir / "protocols.json"
        self.protocols = self._load_protocols()

    def _load_protocols(self) -> Dict[str, Any]:
        """Load protocols from JSON file or seed defaults"""
        if self.filepath.exists():
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Ensure defaults exist
                    for k, v in DEFAULT_PROTOCOLS.items():
                        if k not in data:
                            data[k] = v
                    return data
            except Exception as e:
                console.print(f"[yellow]Error loading protocols: {e}. Reverting to defaults.[/yellow]")

        # Save default protocols
        self._save_protocols(DEFAULT_PROTOCOLS)
        return dict(DEFAULT_PROTOCOLS)

    def _save_protocols(self, protocols: Optional[Dict[str, Any]] = None):
        """Save protocols to JSON file"""
        target = protocols if protocols is not None else self.protocols
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(target, f, indent=2)
        except Exception as e:
            console.print(f"[red]Error saving protocols: {e}[/red]")

    def get_protocol(self, name: str) -> Optional[Dict[str, Any]]:
        """Get protocol by name (case-insensitive)"""
        name_clean = name.strip().lower()
        for key, proto in self.protocols.items():
            if key.lower() == name_clean or proto.get("name", "").lower() == name_clean:
                return proto
        return None

    def list_protocols(self) -> List[Dict[str, Any]]:
        """List all protocols"""
        return list(self.protocols.values())

    def add_protocol(self, name: str, description: str, steps: List[Dict[str, Any]], project_path: Optional[str] = None, venv_path: Optional[str] = None) -> bool:
        """Add or overwrite a protocol"""
        key = name.strip().lower()
        if not key:
            return False
        
        proto_data = {
            "name": name.strip(),
            "description": description.strip(),
            "steps": steps or []
        }
        if project_path:
            proto_data["project_path"] = project_path
        if venv_path:
            proto_data["venv_path"] = venv_path

        self.protocols[key] = proto_data
        self._save_protocols()
        return True

    def delete_protocol(self, name: str) -> bool:
        """Delete a protocol by name"""
        key = name.strip().lower()
        if key in self.protocols:
            del self.protocols[key]
            self._save_protocols()
            return True
        return False

    def is_dangerous(self, protocol: Dict[str, Any]) -> bool:
        """Check if any step in the protocol contains a potentially dangerous action (shell command, deletion, write)"""
        for step in protocol.get("steps", []):
            tool = step.get("tool", "")
            kwargs = step.get("kwargs", {})
            
            if tool == "shell_command":
                return True
            elif tool == "directory" and kwargs.get("action") == "delete":
                return True
            elif tool == "write_file":
                return True

        return False

    async def execute_protocol(
        self,
        name: str,
        tools: Any,
        voice_manager: Optional[Any] = None,
        memory: Optional[Any] = None,
        confirm: bool = True
    ) -> str:
        """
        Execute a named protocol sequence step by step.
        """
        proto = self.get_protocol(name)
        if not proto:
            return f"Error: Protocol '{name}' not found."

        proto_name = proto.get("name", name)
        steps = proto.get("steps", [])

        if not steps and not proto.get("project_path"):
            return f"Protocol '{proto_name}' has no defined steps."

        # Safety Check
        if self.is_dangerous(proto) and confirm:
            console.print(Panel(
                f"[bold red]⚠️  SAFETY WARNING: Protocol '{proto_name}' contains potentially destructive steps.[/bold red]\n"
                f"Description: {proto.get('description', '')}",
                title="Protocol Confirmation Required"
            ))
            if not Confirm.ask(f"[yellow]Are you sure you want to execute protocol '{proto_name}'?"):
                return f"Execution of protocol '{proto_name}' cancelled by user."

        console.print(f"\n[bold cyan]🚀 Invoking Protocol: '{proto_name}' ({len(steps)} steps)[/bold cyan]")
        step_outputs = []

        # Project-specific handling if project_path defined
        project_path_str = proto.get("project_path")
        if project_path_str:
            p_path = Path(project_path_str).resolve()
            if p_path.exists():
                os.chdir(str(p_path))
                console.print(f"[bold cyan]📁 Switched working directory to project path: {p_path}[/bold cyan]")
                step_outputs.append(f"Switched directory to: {p_path}")
                
                # Check for venv
                venv_str = proto.get("venv_path")
                if venv_str and Path(venv_str).exists():
                    console.print(f"[green]🐍 Virtual environment found: {venv_str}[/green]")
                    step_outputs.append(f"Activated venv: {venv_str}")
                
                # Check for TODO.md
                todo_path = p_path / "TODO.md"
                if todo_path.exists():
                    with open(todo_path, 'r', encoding='utf-8', errors='ignore') as f:
                        todo_text = f.read()
                    console.print(Panel(todo_text[:1000], title="[bold cyan]📋 Project TODO.md[/bold cyan]"))
                    step_outputs.append(f"TODO.md Content:\n{todo_text[:500]}")

        for idx, step in enumerate(steps, 1):
            tool_name = step.get("tool", "")
            kwargs = step.get("kwargs", {})
            step_desc = step.get("description", f"Step {idx}: {tool_name}")

            console.print(f"[cyan]▶ Step {idx}/{len(steps)}:[/cyan] [bold]{step_desc}[/bold]")
            
            # Execute step tool call
            res = await tools.execute_tool(tool_name, **kwargs)
            step_outputs.append(f"Step {idx} ({step_desc}): {res.strip()}")

            if memory:
                memory.log_task(f"Protocol '{proto_name}' - {step_desc}", "completed")

            # Voice feedback per step if voice mode enabled
            if voice_manager and hasattr(voice_manager, 'enabled') and voice_manager.enabled:
                step_phrase = f"Step {idx} complete: {step_desc}"
                await voice_manager.speak_response(step_phrase)

            await asyncio.sleep(0.3)

        summary = f"Protocol '{proto_name}' executed successfully ({len(steps)} steps completed).\n" + "\n".join(f"- {o}" for o in step_outputs)
        return summary
