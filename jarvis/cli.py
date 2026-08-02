"""
JARVIS CLI - Main entry point for the terminal AI assistant
"""

import asyncio
import sys
import subprocess
import re
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.live import Live
import yaml

from jarvis.api_client import NIMClient
from jarvis.memory import Memory, CommandLogger
from jarvis.tools import ToolRegistry, WebsiteOpenTool
from jarvis.apps import AppRegistry
from jarvis.voice import VoiceManager, ProactiveMonitor
from jarvis.awareness import GlobalAwarenessManager
from jarvis.protocols import ProtocolManager
from jarvis.ui import ui, UIState


console = ui.console


class JARVISCLI:
    """Main CLI application for JARVIS"""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize JARVIS CLI"""
        self.config = self._load_config(config_path)
        
        # Initialize components
        self.memory = Memory(self.config["memory"]["file"])
        self.api_client = NIMClient(config_path, memory=self.memory)
        self.logger = CommandLogger(self.config["memory"]["log_file"])
        self.app_registry = AppRegistry()
        self.tools = ToolRegistry(
            confirm_dangerous=self.config["tools"]["confirm_dangerous"],
            logger=self.logger if self.config["tools"]["log_commands"] else None,
            app_registry=self.app_registry
        )
        
        # Initialize voice manager
        self.voice_manager = VoiceManager(self.config)
        self.voice_manager.set_callbacks(
            on_transcription=self._handle_voice_transcription,
            on_response=self._handle_voice_response
        )
        
        # Initialize proactive monitor
        self.proactive_monitor = ProactiveMonitor(
            memory=self.memory,
            tts_engine=self.voice_manager.tts,
            check_interval=60
        )
        
        # Initialize global awareness manager
        self.awareness_manager = GlobalAwarenessManager(
            config=self.config,
            api_client=self.api_client,
            proactive_monitor=self.proactive_monitor
        )
        
        # Initialize protocol manager
        self.protocol_manager = ProtocolManager(data_dir="jarvis/data")
        
        # Session state
        self.running = True
        self.command_history = []
        self.voice_input_queue = asyncio.Queue()
        self.is_busy = False  # Track if JARVIS is busy (speaking, recording, etc.)
        self.current_tts_task: Optional[asyncio.Task] = None

    def stop_speech(self):
        """Stop any running TTS task and active audio playback immediately"""
        if self.current_tts_task and not self.current_tts_task.done():
            self.current_tts_task.cancel()
            self.current_tts_task = None
        self.voice_manager.stop_speaking()
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            return {
                "api": {
                    "base_url": "https://integrate.api.nvidia.com/v1",
                    "model": "meta/llama-3.1-8b-instruct",
                    "temperature": 0.7,
                    "max_tokens": 1000,
                    "stream": True
                },
                "memory": {
                    "file": "jarvis_memory.json",
                    "log_file": "jarvis_commands.log"
                },
                "tools": {
                    "confirm_dangerous": True,
                    "log_commands": True
                },
                "voice": {
                    "enabled": False,
                    "stt_model": "base",
                    "tts_engine": "edge",
                    "tts_voice": "en-GB-RyanNeural",
                    "push_to_talk_key": "space",
                    "wake_word_enabled": False,
                    "silence_threshold": 0.5,
                    "auto_stop_recording": True
                },
                "personality": {
                    "user_title": "sir",
                    "response_style": "concise",
                    "enable_boot_greeting": True
                }
            }
    
    def show_banner(self):
        """Display startup banner"""
        ui.show_banner()
    
    def show_help(self):
        """Display help information"""
        help_text = """
[bold cyan]Available Commands:[/bold cyan]

  [bold]/help[/bold]              - Show this help message
  [bold]/clear[/bold]             - Clear the screen
  [bold]/exit[/bold]              - Exit JARVIS
  [bold]/history[/bold]           - Show conversation history
  [bold]/tools[/bold]             - List available tools
  [bold]/reminders[/bold]         - Show your reminders
  [bold]/notes[/bold]             - Show your notes
  [bold]/tasks[/bold]             - Show recent task history
  [bold]/remember <fact>[/bold]    - Manually save a fact about yourself
  [bold]/forget <keyword>[/bold]   - Search and delete facts matching keyword
  [bold]/profile[/bold]           - Show current user profile and memory stats
  [bold]/facts [category][/bold]  - List stored facts (optionally by category)
  [bold]/apps[/bold]              - List registered software applications
  [bold]/addapp <name> <cmd>[/bold]- Register a custom app command or exe path
  [bold]/removeapp <name>[/bold]   - Remove a registered app
  [bold]/voice on[/bold]          - Enable voice mode
  [bold]/voice off[/bold]         - Disable voice mode
  [bold]/awareness on|off[/bold]   - Enable/disable global news monitoring
  [bold]/awareness topics[/bold]   - List/add/remove watched news topics
  [bold]/news[/bold]               - Show recent surfaced notable news updates
  [bold]/protocol list[/bold]       - Show available macro protocols
  [bold]/protocol run <name>[/bold]  - Execute a macro protocol
  [bold]/protocol create <name>[/bold] - Interactively build a new macro protocol
  [bold]/protocol delete <name>[/bold] - Delete a macro protocol
  [bold]/speak on|off[/bold]     - Enable/disable output response speech
  [bold]/mute[/bold]             - Stop currently playing speech immediately

[bold cyan]Natural Language Commands:[/bold cyan]

  "Open notepad" / "Launch chrome"  - Open installed software
  "Open youtube" / "Go to github"    - Open common website
  "Browse to X" / "Search google for X" - Open URL or search
  "Create a folder called X"         - Create directory
  "Read file X"                       - Read file contents
  "List files in X"                   - List directory contents
  "Search for X"                      - Search for files
  "Run command X"                     - Execute shell command
  "Remind me to X"                    - Add a reminder
  "Note: X"                           - Add a note

[bold cyan]Tips:[/bold cyan]
  - JARVIS maintains long-term persistent memory across sessions
  - Dangerous commands require confirmation
  - All commands are logged for safety
"""
        console.print(Panel(help_text, title="[bold cyan]Help[/bold cyan]", border_style="cyan"))

    def show_apps(self):
        """Display registered application launchers"""
        apps = self.app_registry.list_apps()
        
        table = Table(title="[bold cyan]Registered Applications[/bold cyan]")
        table.add_column("App Name / Alias", style="cyan")
        table.add_column("Command / Target Path", style="white")
        
        for name, cmd in sorted(apps.items()):
            table.add_row(name, cmd)
            
        console.print(table)

    def handle_addapp(self, args_str: str) -> str:
        """Handle /addapp <name> <command>"""
        parts = args_str.strip().split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /addapp <name> <path_or_command>"
        
        name, cmd = parts[0], parts[1]
        success = self.app_registry.add_app(name, cmd)
        if success:
            return f"Registered app '[cyan]{name}[/cyan]' -> '{cmd}'"
        else:
            return "Error registering app. Invalid name or command."

    def handle_removeapp(self, name: str) -> str:
        """Handle /removeapp <name>"""
        name_clean = name.strip()
        if not name_clean:
            return "Usage: /removeapp <name>"
        
        success = self.app_registry.remove_app(name_clean)
        if success:
            return f"Removed app registration for '[cyan]{name_clean}[/cyan]'"
        else:
            return f"App '[cyan]{name_clean}[/cyan]' was not found in registry."

    def show_profile(self):
        """Display current stored profile and total fact count"""
        profile = self.memory.get_profile()
        facts = self.memory.get_facts()
        
        table = Table(title="[bold cyan]User Profile[/bold cyan]")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        
        if profile:
            for k, v in profile.items():
                table.add_row(str(k), str(v))
        else:
            table.add_row("(none)", "No profile attributes saved yet.")
            
        console.print(table)
        console.print(f"[dim]Total stored facts in memory: [cyan]{len(facts)}[/cyan][/dim]\n")

    def show_facts(self, category: Optional[str] = None):
        """Display facts in database, optionally filtered by category"""
        facts = self.memory.get_facts(category)
        
        if not facts:
            cat_str = f" in category '{category}'" if category else ""
            console.print(f"[yellow]No facts stored{cat_str}.[/yellow]")
            return
        
        title = f"[bold cyan]Stored Facts ({category})[/bold cyan]" if category else "[bold cyan]Stored Facts[/bold cyan]"
        table = Table(title=title)
        table.add_column("ID", style="cyan")
        table.add_column("Category", style="green")
        table.add_column("Fact Content", style="white")
        table.add_column("Source", style="dim")
        
        for f in facts:
            table.add_row(
                str(f["id"]),
                f["category"],
                f["content"],
                f.get("source", "auto")
            )
        
        console.print(table)

    def handle_remember(self, fact_text: str) -> str:
        """Handle /remember <fact> command"""
        if not fact_text.strip():
            return "Usage: /remember <fact to remember>"
        
        category = "general"
        content = fact_text.strip()
        if ":" in fact_text and not fact_text.startswith("http"):
            parts = fact_text.split(":", 1)
            if len(parts[0].strip().split()) == 1:
                category = parts[0].strip().lower()
                content = parts[1].strip()
        
        saved = self.memory.add_fact(category=category, content=content, source="manual", confidence="high")
        if saved:
            return f"Fact remembered ([cyan]{category}[/cyan]): {content}"
        else:
            return f"Fact already known or duplicate: {content}"

    def handle_forget(self, keyword: str) -> str:
        """Handle /forget <keyword> command"""
        if not keyword.strip():
            return "Usage: /forget <keyword>"
        
        matches = self.memory.search_facts(keyword)
        if not matches:
            return f"No facts found matching '{keyword}'."
        
        table = Table(title=f"[bold yellow]Facts Matching '{keyword}'[/bold yellow]")
        table.add_column("ID", style="cyan")
        table.add_column("Category", style="green")
        table.add_column("Content", style="white")
        
        for m in matches:
            table.add_row(str(m["id"]), m["category"], m["content"])
        
        console.print(table)
        
        from rich.prompt import Confirm
        if Confirm.ask(f"[yellow]Are you sure you want to delete these {len(matches)} fact(s)?"):
            deleted = self.memory.delete_facts_by_keyword(keyword)
            return f"Successfully deleted {len(deleted)} fact(s)."
        else:
            return "Operation cancelled. No facts were deleted."
    
    def show_tools(self):
        """Display available tools"""
        tools_list = self.tools.list_tools()
        
        table = Table(title="[bold cyan]Available Tools[/bold cyan]")
        table.add_column("Tool Name", style="cyan")
        table.add_column("Description", style="white")
        
        for tool in tools_list:
            table.add_row(tool["name"], tool["description"])
        
        console.print(table)
    
    def show_reminders(self):
        """Display reminders"""
        reminders = self.memory.get_reminders()
        
        if not reminders:
            console.print("[yellow]No reminders set.[/yellow]")
            return
        
        table = Table(title="[bold cyan]Reminders[/bold cyan]")
        table.add_column("ID", style="cyan")
        table.add_column("Text", style="white")
        table.add_column("Status", style="green")
        table.add_column("Due Date", style="white")
        
        for reminder in reminders:
            status = "[green]✓[/green]" if reminder["completed"] else "[yellow]○[/yellow]"
            table.add_row(
                str(reminder["id"]),
                reminder["text"],
                status,
                reminder.get("due_date", "No due date")
            )
        
        console.print(table)
    
    def show_notes(self):
        """Display notes"""
        notes = self.memory.get_notes()
        
        if not notes:
            console.print("[yellow]No notes saved.[/yellow]")
            return
        
        table = Table(title="[bold cyan]Notes[/bold cyan]")
        table.add_column("ID", style="cyan")
        table.add_column("Category", style="cyan")
        table.add_column("Text", style="white")
        table.add_column("Date", style="white")
        
        for note in notes:
            table.add_row(
                str(note["id"]),
                note["category"],
                note["text"],
                note["created_at"][:10]
            )
        
        console.print(table)
    
    def show_tasks(self):
        """Display recent task history"""
        tasks = self.memory.get_recent_tasks()
        
        if not tasks:
            console.print("[yellow]No task history.[/yellow]")
            return
        
        table = Table(title="[bold cyan]Recent Tasks[/bold cyan]")
        table.add_column("Task", style="white")
        table.add_column("Result", style="green")
        table.add_column("Time", style="cyan")
        
        for task in tasks:
            table.add_row(
                task["task"],
                task["result"],
                task["timestamp"][:19]
            )
        
        console.print(table)
    
    def show_history(self):
        """Display conversation history"""
        if not self.api_client.messages:
            console.print("[yellow]No conversation history.[/yellow]")
            return
        
        for msg in self.api_client.messages:
            role_color = "cyan" if msg["role"] == "user" else "green"
            console.print(f"[{role_color}]{msg['role'].upper()}:[/{role_color}] {msg['content']}\n")
    
    def _split_instructions(self, user_input: str) -> list:
        """
        Split a compound user input into individual actionable instructions.
        E.g. "open notepad and create a folder called test and remind me to call mom"
        -> ["open notepad", "create a folder called test", "remind me to call mom"]
        """
        text = user_input.strip()
        if not text:
            return []
            
        # Split on explicit newlines and semicolons first
        raw_parts = re.split(r'[\n;]+', text)
        
        action_keywords = (
            "open", "launch", "start", "run", "browse", "search", "create", "make",
            "read", "list", "delete", "execute", "remind", "note:", "remember",
            "forget", "tell", "explain", "what", "how", "show", "display", "give", "write",
            "addapp", "removeapp", "/help", "/clear", "/exit", "/history", "/tools",
            "/reminders", "/notes", "/tasks", "/profile", "/apps", "/facts", "/remember",
            "/forget", "/voice"
        )
        
        instructions = []
        
        for part in raw_parts:
            part = part.strip()
            if not part:
                continue
                
            # Split candidate conjunctions/separators: " and then ", ", then ", " then ", ", and ", " and ", " also ", " plus ", ", "
            pattern = r'(?:\s*,\s*then\s+|\s+and\s+then\s+|\s+then\s+|\s*,\s*and\s+|\s+and\s+|\s+also\s+|\s+plus\s+|\s*,\s*)'
            tokens = re.split(pattern, part, flags=re.IGNORECASE)
            
            if len(tokens) <= 1:
                instructions.append(part)
            else:
                current_inst = tokens[0].strip()
                for next_token in tokens[1:]:
                    next_token_clean = next_token.strip()
                    first_word = next_token_clean.split()[0].lower() if next_token_clean.split() else ""
                    
                    if first_word in action_keywords or ":" in first_word or next_token_clean.lower().startswith("note:"):
                        if current_inst:
                            instructions.append(current_inst)
                        current_inst = next_token_clean
                    else:
                        current_inst += f", {next_token_clean}"
                if current_inst:
                    instructions.append(current_inst)
                    
        return instructions if instructions else [text]

    async def process_single_command(self, user_input: str) -> Optional[str]:
        """Process a single instruction input and return response"""
        user_input = user_input.strip()
        if not user_input:
            return None
        
        # Handle slash commands
        if user_input.startswith("/"):
            return await self._handle_slash_command(user_input)

        # Check for coding tasks and delegate to Claude Code
        if self._is_coding_task(user_input):
            return await self._delegate_to_claude_code(user_input)

        # Check for natural language tool commands
        tool_response = await self._check_tool_commands(user_input)
        if tool_response:
            return tool_response

        # Otherwise, send to AI
        return await self._get_ai_response(user_input)

    async def process_command(self, user_input: str) -> Optional[str]:
        """Process user input (single or multiple instructions) and return response"""
        user_input = user_input.strip()
        if not user_input:
            return None

        # Add to command history
        self.command_history.append(user_input)

        # Handle single slash commands directly
        if user_input.startswith("/"):
            return await self._handle_slash_command(user_input)

        instructions = self._split_instructions(user_input)

        if len(instructions) <= 1:
            target_inst = instructions[0] if instructions else user_input
            return await self.process_single_command(target_inst)

        # Process multiple instructions sequentially
        console.print(f"[dim cyan]Processing {len(instructions)} instructions...[/dim cyan]")
        results = []
        for idx, inst in enumerate(instructions, 1):
            res = await self.process_single_command(inst)
            if res:
                results.append(f"{idx}. {res.strip()}")

        if results:
            return "\n".join(results)
        return "All instructions executed."

    async def _handle_slash_command(self, command: str) -> str:
        """Handle slash commands"""
        cmd_raw = command.strip()
        cmd_lower = cmd_raw.lower()
        
        if cmd_lower == "/help":
            self.show_help()
            return "Here are the available commands and natural language options, sir."
        elif cmd_lower == "/clear":
            console.clear()
            self.show_banner()
            return "Console cleared, sir."
        elif cmd_lower == "/exit":
            self.running = False
            return "Goodbye! Have a great day!"
        elif cmd_lower == "/history":
            self.show_history()
            return "Displaying conversation history, sir."
        elif cmd_lower == "/tools":
            self.show_tools()
            return "Displaying available tools, sir."
        elif cmd_lower == "/reminders":
            self.show_reminders()
            return "Displaying your reminders, sir."
        elif cmd_lower == "/notes":
            self.show_notes()
            return "Displaying your saved notes, sir."
        elif cmd_lower == "/tasks":
            self.show_tasks()
            return "Displaying recent task history, sir."
        elif cmd_lower == "/profile":
            self.show_profile()
            return "Displaying user profile statistics, sir."
        elif cmd_lower == "/apps":
            self.show_apps()
            return "Displaying registered applications, sir."
        elif cmd_lower.startswith("/addapp"):
            parts = cmd_raw.split(maxsplit=1)
            args_str = parts[1] if len(parts) > 1 else ""
            return self.handle_addapp(args_str)
        elif cmd_lower.startswith("/removeapp"):
            parts = cmd_raw.split(maxsplit=1)
            name = parts[1] if len(parts) > 1 else ""
            return self.handle_removeapp(name)
        elif cmd_lower.startswith("/facts"):
            parts = cmd_raw.split(maxsplit=1)
            category = parts[1] if len(parts) > 1 else None
            self.show_facts(category)
            return "Displaying stored facts, sir."
        elif cmd_lower.startswith("/remember"):
            parts = cmd_raw.split(maxsplit=1)
            fact_text = parts[1] if len(parts) > 1 else ""
            return self.handle_remember(fact_text)
        elif cmd_lower.startswith("/forget"):
            parts = cmd_raw.split(maxsplit=1)
            keyword = parts[1] if len(parts) > 1 else ""
            return self.handle_forget(keyword)
        elif cmd_lower == "/voice on":
            self.voice_manager.enable()
            return "Voice mode enabled. Hold spacebar to record."
        elif cmd_lower == "/voice off":
            self.voice_manager.disable()
            return "Voice mode disabled."
        elif cmd_lower == "/speak on":
            self.voice_manager.speak_responses = True
            return "Output-only response speech enabled, sir."
        elif cmd_lower == "/speak off":
            self.voice_manager.speak_responses = False
            self.stop_speech()
            return "Output-only response speech disabled, sir."
        elif cmd_lower in ["/mute", "/stop"]:
            self.stop_speech()
            return "Muted active speech playback, sir."
        elif cmd_lower.startswith("/awareness"):
            return self.handle_awareness_command(cmd_raw)
        elif cmd_lower == "/news":
            self.show_news()
            return "Displaying recent surfaced news updates, sir."
        elif cmd_lower.startswith("/protocol"):
            return await self.handle_protocol_command(cmd_raw)
        else:
            return f"Unknown command: {command}. Type /help for available commands."

    def show_protocols(self):
        """Display registered protocols"""
        protos = self.protocol_manager.list_protocols()
        
        table = Table(title="[bold cyan]Available JARVIS Protocols[/bold cyan]")
        table.add_column("Protocol Name", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Steps Count", style="yellow")
        table.add_column("Safety Level", style="green")
        
        for p in protos:
            dangerous = self.protocol_manager.is_dangerous(p)
            safety = "[red]⚠️ Requires Confirmation[/red]" if dangerous else "[green]✓ Standard[/green]"
            table.add_row(
                p.get("name", ""),
                p.get("description", ""),
                str(len(p.get("steps", []))),
                safety
            )
            
        console.print(table)

    async def handle_protocol_command(self, command_str: str) -> str:
        """Handle /protocol [list|run|create|delete] commands"""
        parts = command_str.strip().split(maxsplit=2)
        subcmd = parts[1].lower() if len(parts) > 1 else "list"
        
        if subcmd == "list":
            self.show_protocols()
            return "Displaying available JARVIS protocols, sir."
            
        elif subcmd in ["run", "execute", "invoke"]:
            if len(parts) < 3:
                return "Usage: /protocol run <protocol_name>"
            p_name = parts[2].strip()
            return await self.protocol_manager.execute_protocol(
                name=p_name,
                tools=self.tools,
                voice_manager=self.voice_manager,
                memory=self.memory
            )
            
        elif subcmd in ["create", "add"]:
            if len(parts) < 3:
                return "Usage: /protocol create <protocol_name>"
            p_name = parts[2].strip()
            
            console.print(f"[cyan]Creating protocol '[bold]{p_name}[/bold]'...[/cyan]")
            desc = await asyncio.to_thread(Prompt.ask, "Enter protocol description", default=f"Custom macro protocol: {p_name}")
            
            steps = []
            console.print("\n[yellow]Add steps (e.g. 'open vscode', 'open github', 'create folder test')[/yellow]")
            console.print("[dim]Type 'done' or 'finish' when complete.[/dim]\n")
            
            step_idx = 1
            while True:
                step_input = await asyncio.to_thread(Prompt.ask, f"Step {step_idx} (command or 'done')")
                step_clean = step_input.strip()
                if not step_clean or step_clean.lower() in ["done", "finish", "exit", "stop"]:
                    break
                
                tool_name = "shell_command"
                kwargs = {"command": step_clean}
                
                inp_lower = step_clean.lower()
                if inp_lower.startswith("open ") or inp_lower.startswith("launch "):
                    target = step_clean.split(maxsplit=1)[1].strip() if len(step_clean.split()) > 1 else ""
                    if any(site in target.lower() for site in ["youtube", "github", "gmail", "google"]):
                        tool_name = "open_website"
                        kwargs = {"site_name": target}
                    else:
                        tool_name = "open_application"
                        kwargs = {"app_name": target}
                elif inp_lower.startswith("create folder ") or inp_lower.startswith("make folder "):
                    folder = step_clean.split()[-1]
                    tool_name = "directory"
                    kwargs = {"action": "create", "path": folder}
                
                steps.append({
                    "tool": tool_name,
                    "kwargs": kwargs,
                    "description": step_clean
                })
                step_idx += 1
                
            if not steps:
                return "Protocol creation cancelled (no steps added)."
                
            added = self.protocol_manager.add_protocol(p_name, desc, steps)
            if added:
                return f"Protocol '[cyan]{p_name}[/cyan]' created with {len(steps)} steps, sir."
            else:
                return "Error creating protocol."
                
        elif subcmd in ["delete", "remove"]:
            if len(parts) < 3:
                return "Usage: /protocol delete <protocol_name>"
            p_name = parts[2].strip()
            deleted = self.protocol_manager.delete_protocol(p_name)
            if deleted:
                return f"Protocol '[cyan]{p_name}[/cyan]' deleted successfully, sir."
            else:
                return f"Protocol '{p_name}' not found."
                
        else:
            return "Usage: /protocol [list|run <name>|create <name>|delete <name>]"

    def show_news(self):
        """Display recent surfaced news items"""
        news_items = self.awareness_manager.get_surfaced_news(limit=15)
        
        if not news_items:
            console.print("[yellow]No surfaced news items yet. Background monitoring is running.[/yellow]")
            return
        
        table = Table(title="[bold cyan]Surfaced News Updates[/bold cyan]")
        table.add_column("Topic", style="cyan")
        table.add_column("Headline", style="white")
        table.add_column("Score", style="yellow")
        table.add_column("Time", style="dim")
        table.add_column("Link / URL", style="blue")
        
        for item in news_items:
            table.add_row(
                item.get("topic", "General"),
                item.get("headline", ""),
                str(item.get("score", "-")),
                item.get("timestamp", "")[:16].replace("T", " "),
                item.get("link", "")
            )
        
        console.print(table)

    def handle_awareness_command(self, command_str: str) -> str:
        """Handle /awareness [on|off|topics|add|remove|check] commands"""
        parts = command_str.strip().split(maxsplit=2)
        subcmd = parts[1].lower() if len(parts) > 1 else "topics"
        
        if subcmd == "on":
            self.awareness_manager.set_enabled(True)
            return "Global Awareness background monitor enabled, sir."
        elif subcmd == "off":
            self.awareness_manager.set_enabled(False)
            return "Global Awareness background monitor disabled, sir."
        elif subcmd == "check":
            asyncio.create_task(self.awareness_manager.check_news())
            return "Triggered immediate Global Awareness news check in background, sir."
        elif subcmd in ["topics", "topic"]:
            if len(parts) > 2:
                sub_parts = parts[2].split(maxsplit=1)
                action = sub_parts[0].lower()
                topic_val = sub_parts[1] if len(sub_parts) > 1 else ""
                
                if action == "add" and topic_val:
                    added = self.awareness_manager.add_topic(topic_val)
                    if added:
                        return f"Added watched topic: '[cyan]{topic_val}[/cyan]', sir."
                    else:
                        return f"Topic '[cyan]{topic_val}[/cyan]' is already being watched."
                elif action in ["remove", "delete"] and topic_val:
                    removed = self.awareness_manager.remove_topic(topic_val)
                    if removed:
                        return f"Removed watched topic: '[cyan]{topic_val}[/cyan]', sir."
                    else:
                        return f"Topic '[cyan]{topic_val}[/cyan]' was not found."
            
            topics = self.awareness_manager.get_topics()
            status_str = "Enabled" if self.awareness_manager.enabled else "Disabled"
            console.print(f"[bold cyan]Global Awareness Watched Topics[/bold cyan] ({status_str}):")
            for idx, t in enumerate(topics, 1):
                console.print(f"  {idx}. [white]{t}[/white]")
            console.print("[dim]\nUse '/awareness topics add <topic>' or '/awareness topics remove <topic>' to edit.[/dim]")
            return "Displaying watched news topics, sir."
        elif subcmd == "add" and len(parts) > 2:
            topic_val = parts[2]
            added = self.awareness_manager.add_topic(topic_val)
            if added:
                return f"Added watched topic: '[cyan]{topic_val}[/cyan]', sir."
            else:
                return f"Topic '[cyan]{topic_val}[/cyan]' is already being watched."
        elif subcmd in ["remove", "delete"] and len(parts) > 2:
            topic_val = parts[2]
            removed = self.awareness_manager.remove_topic(topic_val)
            if removed:
                return f"Removed watched topic: '[cyan]{topic_val}[/cyan]', sir."
            else:
                return f"Topic '[cyan]{topic_val}[/cyan]' was not found."
        else:
            return "Usage: /awareness [on|off|topics|add <topic>|remove <topic>|check]"
    
    async def _check_tool_commands(self, user_input: str) -> Optional[str]:
        """Check if input matches a tool command or protocol trigger"""
        input_lower = user_input.lower()
        
        # Natural Language Protocol Triggers
        if hasattr(self, 'protocol_manager'):
            for proto in self.protocol_manager.list_protocols():
                p_name = proto["name"].lower()
                triggers = [
                    f"activate {p_name} protocol",
                    f"activate {p_name}",
                    f"run {p_name} protocol",
                    f"run protocol {p_name}",
                    f"execute {p_name} protocol",
                    f"invoke {p_name} protocol",
                    f"start {p_name} protocol",
                    f"protocol {p_name}",
                    f"{p_name} protocol"
                ]
                if any(trig == input_lower or trig in input_lower for trig in triggers):
                    return await self.protocol_manager.execute_protocol(
                        name=p_name,
                        tools=self.tools,
                        voice_manager=self.voice_manager,
                        memory=self.memory
                    )
        
        # Open Application or Website
        for prefix in ["open ", "launch ", "start ", "run "]:
            if input_lower.startswith(prefix):
                target = user_input[len(prefix):].strip()
                target_lower = target.lower()
                
                # Exclude folder/directory/file commands
                if not ("folder" in target_lower or "directory" in target_lower or "file" in target_lower or "command" in target_lower):
                    if target_lower in WebsiteOpenTool.SITE_ALIASES or any(site in target_lower for site in ["youtube", "github", "gmail", "google", "reddit", "twitter"]):
                        result = await self.tools.execute_tool("open_website", site_name=target)
                        self.memory.log_task(f"Open website {target}", "completed")
                        return result
                    
                    cmd, matches = self.app_registry.resolve_app(target)
                    if cmd or matches or target_lower in ["notepad", "calc", "calculator", "chrome", "vscode", "explorer", "task manager", "settings"]:
                        result = await self.tools.execute_tool("open_application", app_name=target)
                        self.memory.log_task(f"Open application {target}", "completed")
                        return result

        # Web Search / Browse URL
        if "browse to" in input_lower or "search google for" in input_lower or input_lower.startswith("search web for"):
            for prefix in ["browse to", "search google for", "search web for"]:
                if prefix in input_lower:
                    query = user_input[input_lower.index(prefix) + len(prefix):].strip()
                    if query:
                        result = await self.tools.execute_tool("open_url", url_or_query=query)
                        self.memory.log_task(f"Browse/Search {query}", "completed")
                        return result

        # Create folder/directory
        if ("create" in input_lower or "make" in input_lower) and ("folder" in input_lower or "directory" in input_lower):
            folder_name = re.sub(r'^(create|make)\s+(a\s+)?(folder|directory)(\s+(called|named))?\s*', '', user_input, flags=re.I).strip()
            if not folder_name:
                folder_name = "new_folder"
            result = await self.tools.execute_tool("directory", action="create", path=folder_name)
            self.memory.log_task(f"Create folder {folder_name}", "completed")
            return result
        
        # Read file
        elif ("read" in input_lower or "view" in input_lower or "cat" in input_lower) and "file" in input_lower:
            filename = re.sub(r'^(read|view|cat)\s+(the\s+)?(contents\s+of\s+)?(file\s+)?', '', user_input, flags=re.I).strip()
            if filename:
                result = await self.tools.execute_tool("read_file", filepath=filename)
                self.memory.log_task(f"Read file {filename}", "completed")
                return result
        
        # List files
        elif "list" in input_lower and ("file" in input_lower or "directory" in input_lower):
            directory = "."
            words = user_input.split()
            if "in" in words:
                try:
                    idx = words.index("in")
                    if idx + 1 < len(words):
                        directory = words[idx + 1]
                except ValueError:
                    pass
            result = await self.tools.execute_tool("list_files", directory=directory)
            self.memory.log_task(f"List files in {directory}", "completed")
            return result
        
        # Search files
        elif "search" in input_lower and not ("google" in input_lower or "web" in input_lower):
            pattern = re.sub(r'^(search|find)\s+(for\s+)?(files?\s*)?(matching\s+)?', '', user_input, flags=re.I).strip()
            if not pattern:
                pattern = "*"
            result = await self.tools.execute_tool("search_files", pattern=pattern)
            self.memory.log_task(f"Search for {pattern}", "completed")
            return result
        
        # Run command
        elif "run command" in input_lower or "execute command" in input_lower:
            words = user_input.split()
            if len(words) > 1:
                try:
                    cmd_start = words.index("run") if "run" in words else words.index("execute")
                    command = " ".join(words[cmd_start + 1:])
                    result = await self.tools.execute_tool("shell_command", command=command)
                    self.memory.log_task(f"Execute command: {command}", "completed")
                    return result
                except ValueError:
                    return "Please specify a command to run"
        
        # Add reminder
        elif "remind" in input_lower:
            reminder_text = re.sub(r'^(remind\s+(me\s+)?(to\s+)?|set\s+a\s+reminder\s+(to\s+)?)', '', user_input, flags=re.I).strip()
            if reminder_text:
                reminder = self.memory.add_reminder(reminder_text)
                return f"Reminder added: {reminder_text}"
        
        # Add note
        elif input_lower.startswith("note:") or input_lower.startswith("save note:") or input_lower.startswith("add note:"):
            note_text = re.sub(r'^(note:|save\s+note:?|add\s+note:?)\s*', '', user_input, flags=re.I).strip()
            if note_text:
                self.memory.add_note(note_text)
                return f"Note saved: {note_text}"
        
        return None
    
    async def _get_ai_response(self, user_input: str) -> str:
        """Get AI response from NVIDIA NIM API"""
        response_text = ""
        ui.set_state(UIState.THINKING)
        
        with console.status("[bold cyan]🧠 JARVIS is thinking...[/bold cyan]") as status:
            async for chunk in self.api_client.chat_stream(user_input):
                response_text += chunk
                status.update(f"[bold cyan]JARVIS:[/bold cyan] {response_text[-50:]}")
        
        return response_text
    
    def _handle_voice_transcription(self, text: str):
        """Handle voice transcription callback"""
        # Put transcription in queue for async processing
        asyncio.create_task(self.voice_input_queue.put(text))
    
    def _handle_voice_response(self, sentence: str):
        """Handle voice TTS sentence callback"""
        console.print(f"[dim cyan]Speaking: {sentence}[/dim cyan]")
    
    def _is_coding_task(self, user_input: str) -> bool:
        """
        Classify if user input is a coding task that should be delegated to Claude Code
        
        Args:
            user_input: User's input text
            
        Returns:
            True if this is a coding task, False otherwise
        """
        coding_keywords = [
            "write a script", "create a script", "build a script",
            "refactor", "debug", "fix the bug", "find the bug",
            "add a function", "implement", "write code for",
            "edit multiple files", "modify files", "update files",
            "create a class", "add a class", "write a module",
            "add tests", "write tests", "test this",
            "code review", "review the code", "optimize",
            "add feature", "implement feature", "build feature"
        ]
        
        input_lower = user_input.lower()
        return any(keyword in input_lower for keyword in coding_keywords)
    
    async def _delegate_to_claude_code(self, task: str) -> str:
        """
        Delegate a coding task to Claude Code CLI
        
        Args:
            task: The task description
            
        Returns:
            Summary of Claude Code's response
        """
        console.print("[cyan]Handing this to Claude Code, sir.[/cyan]")
        
        try:
            # Run claude CLI with the task
            process = await asyncio.create_subprocess_exec(
                "claude",
                task,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = await process.communicate()
            
            if stdout:
                # Stream the output
                console.print(Panel(
                    stdout,
                    title="[bold yellow]Claude Code Output[/bold yellow]",
                    border_style="yellow"
                ))
                
                # Generate a short summary
                summary = self._generate_claude_summary(stdout)
                return summary
            elif stderr:
                console.print(f"[red]Claude Code error: {stderr}[/red]")
                return "Claude Code encountered an error."
            else:
                return "Claude Code completed with no output."
                
        except FileNotFoundError:
            console.print("[yellow]Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code[/yellow]")
            return "Claude Code CLI not available."
        except Exception as e:
            console.print(f"[red]Error delegating to Claude Code: {e}[/red]")
            return f"Error: {str(e)}"
    
    def _generate_claude_summary(self, output: str) -> str:
        """
        Generate a short summary of Claude Code's output
        
        Args:
            output: Claude Code's output text
            
        Returns:
            Short summary
        """
        lines = output.strip().split('\n')
        
        # Look for completion indicators
        completion_indicators = ["done", "completed", "finished", "success", "created", "added", "fixed"]
        
        for line in reversed(lines[:10]):  # Check last 10 lines
            line_lower = line.lower()
            if any(indicator in line_lower for indicator in completion_indicators):
                return line.strip()
        
        # Default summary
        return "Task completed by Claude Code."
    
    async def run(self):
        """Main REPL loop"""
        self.show_banner()
        
        # Start proactive monitor & awareness manager
        self.proactive_monitor.start()
        self.awareness_manager.start()
        
        # Boot greeting if enabled
        personality_config = self.config.get("personality", {})
        if personality_config.get("enable_boot_greeting", True):
            user_title = self.api_client.user_title
            await self.proactive_monitor.speak_boot_greeting(user_title)
        
        while self.running:
            try:
                # Check for voice input with timeout
                try:
                    user_input = await asyncio.wait_for(
                        self.voice_input_queue.get(),
                        timeout=0.1
                    )
                    # Voice input received
                    console.print(f"[bold cyan]You (voice):[/bold cyan] {user_input}")
                except asyncio.TimeoutError:
                    # No voice input, get text input in a separate thread so event loop stays responsive
                    ui.set_state(UIState.IDLE)
                    user_input = await asyncio.to_thread(
                        ui.get_user_input
                    )
                
                if not user_input:
                    continue
                
                # Stop previous speech and cancel active speech task immediately on new message
                self.stop_speech()
                
                # Set busy state
                self.is_busy = True
                self.proactive_monitor.set_busy(True)
                
                # Process input
                response = await self.process_command(user_input)
                
                if response:
                    # Display response using HUD UI panel
                    ui.render_response(response)
                    
                    # Stop any transient speech and start new response speech task
                    self.stop_speech()
                    if self.voice_manager.speak_responses or self.voice_manager.enabled:
                        self.current_tts_task = asyncio.create_task(
                            self.voice_manager.speak_response(response)
                        )
                    
                    ui.set_state(UIState.IDLE)
                    
                    # Log conversation turn & auto-extract durable facts if not a slash command
                    if not user_input.startswith("/"):
                        self.memory.log_conversation_message("user", user_input)
                        self.memory.log_conversation_message("assistant", response)
                        asyncio.create_task(self.api_client.extract_and_save_facts(user_input, response))
                else:
                    ui.set_state(UIState.IDLE)
                
                # Clear busy state
                self.is_busy = False
                self.proactive_monitor.set_busy(False)
                
                # Exit if requested
                if not self.running:
                    break
                    
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted. Type /exit to quit.[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {str(e)}[/red]")
                self.is_busy = False
                self.proactive_monitor.set_busy(False)
        
        # Cleanup
        self.proactive_monitor.stop()
        self.awareness_manager.stop()
        if self.voice_manager.enabled:
            self.voice_manager.disable()
        
        console.print("\n[bold cyan]JARVIS session ended.[/bold cyan]")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="JARVIS - Your Terminal AI Assistant")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    args = parser.parse_args()
    
    cli = JARVISCLI(args.config)
    asyncio.run(cli.run())


if __name__ == "__main__":
    main()
