"""
JARVIS CLI - Main entry point for the terminal AI assistant
"""

import asyncio
import sys
import subprocess
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
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
from jarvis.projects import ProjectManager
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
        self.project_manager = ProjectManager()
        self.api_client = NIMClient(config_path, memory=self.memory, project_manager=self.project_manager)
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
            check_interval=60,
            api_client=self.api_client,
            project_manager=self.project_manager
        )
        self.proactive_monitor.start()
        
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
    
    def show_help(self, category_filter: Optional[str] = None):
        """Display help information, organized into categories and optionally filtered"""
        cat_lower = category_filter.strip().lower() if category_filter else None
        
        categories = {
            "CORE": [
                ("/help [category]", "Show help message (optionally by category)"),
                ("/clear", "Clear the screen"),
                ("/exit", "Exit JARVIS"),
                ("/history", "Show conversation history"),
                ("/tools", "List available tools")
            ],
            "VOICE": [
                ("/speak on|off", "Toggle spoken response output"),
                ("/mute (or /stop)", "Stop active speech playback immediately"),
                ("/voice on|off", "Enable or disable voice input mode")
            ],
            "MEMORY": [
                ("/remember <fact>", "Save a fact manually"),
                ("/forget <keyword>", "Search and remove a stored fact"),
                ("/profile", "Show stored profile and memory stats"),
                ("/facts [category]", "List facts in a category"),
                ("/notes", "Show saved notes"),
                ("/tasks", "Show recent task execution history"),
                ("/whoami (or /recall)", "Summarize profile facts JARVIS knows about you")
            ],
            "REMINDERS & DEADLINES": [
                ("/reminders", "Show current pending reminders"),
                ("/deadline add \"<name>\" <date>", "Add a deadline"),
                ("/deadlines", "List upcoming deadlines with remaining time")
            ],
            "APPS & SYSTEM": [
                ("/apps", "List registered software applications"),
                ("/addapp <name> <path>", "Register a new custom app path/exe"),
                ("/removeapp <name>", "Remove a registered application launcher")
            ],
            "PROTOCOLS": [
                ("/protocol list", "Show all macro protocols"),
                ("/protocol run <name>", "Execute a macro protocol or project"),
                ("/protocol create <name>", "Build a new macro protocol"),
                ("/protocol delete <name>", "Delete a macro protocol")
            ],
            "STUDY TOOLS": [
                ("/flashcard add \"<q>\" \"<a>\"", "Add a flashcard to database"),
                ("/flashcard from-file <path>", "Generate flashcards from notes file"),
                ("/review", "Start interactive flashcard quiz session"),
                ("/summarize <path.pdf>", "Extract and summarize an academic PDF")
            ],
            "DEVELOPER": [
                ("/explain-error [error]", "Explain traceback error and fix steps"),
                ("\"what's my git status\"", "Show real git status, branch, and recent commit")
            ],
            "IDEAS & NOTES": [
                ("/idea <text>", "Save a business/project idea"),
                ("/ideas list", "List all saved ideas"),
                ("/ideas search <term>", "Search saved ideas"),
                ("/meeting prep <person/topic>", "Briefing from stored memory facts")
            ],
            "TRADING": [
                ("/watch <ticker> <condition> <price>", "Add stock price alert (e.g. /watch AAPL above 200)"),
                ("/trade log <ticker> <BUY/SELL> <price> <qty>", "Log a trade to journal"),
                ("/trade review [ticker]", "View trade journal history")
            ],
            "DIAGNOSTICS & TRUST": [
                ("/diagnose", "Check real status of all subsystems (DB, API, audio, threads)"),
                ("/why", "Show what tool was called and why for the last response"),
                ("/why <n>", "Show tool details for the nth-previous response")
            ],
            "GLOBAL AWARENESS": [
                ("/awareness on|off|topics", "Manage background news monitoring"),
                ("/news", "Show recent surfaced notable news updates")
            ],
            "SYSTEM MONITORING": [
                ("/system", "Real-time snapshot of CPU, RAM, GPU, disk, and network"),
                ("/system log", "Show recent system resource anomaly logs")
            ],
            "WEATHER": [
                ("/weather", "Current conditions and today's forecast for configured city"),
                ("/weather tomorrow", "Tomorrow's weather forecast")
            ],
            "GOOGLE CALENDAR": [
                ("/calendar today", "List today's scheduled calendar events"),
                ("/calendar tomorrow", "List tomorrow's scheduled calendar events"),
                ("/calendar next", "Show next upcoming calendar event")
            ],
            "EMAIL TRIAGE": [
                ("/email", "Show last 5 unread inbox messages"),
                ("/email read <n>", "Read the nth unread email body"),
                ("/email summary", "LLM briefing summary of all unread emails")
            ],
            "DUCKDUCKGO WEB SEARCH": [
                ("/search <query>", "Perform real-time DuckDuckGo web search"),
                ("/search ddg <query>", "DuckDuckGo web search with AI voice response")
            ],
            "PROJECTS": [
                ("/projects", "List all active projects with status and task count"),
                ("/projects all", "Include paused and completed projects"),
                ("/projects <name>", "Full briefing on one project"),
                ("/projects add", "Guided flow to create new project"),
                ("/task add <project> <task>", "Quick add a task"),
                ("/task done <project> <task>", "Mark a task complete"),
                ("/task list <project>", "List tasks for a project"),
                ("/tasks overdue", "All overdue tasks across all projects"),
                ("/decide <project> <decision>", "Log a project decision"),
                ("/note <project> <text>", "Add a note to a project"),
                ("/timeline <project>", "Show project timeline"),
                ("/milestone <project> <event>", "Add milestone to timeline")
            ]
        }
        
        # Filter categories if requested
        if cat_lower:
            matched_cats = {k: v for k, v in categories.items() if cat_lower in k.lower() or (cat_lower in ["projects", "project", "task", "tasks"] and "PROJECTS" in k) or (cat_lower in ["dev", "swe"] and "DEVELOPER" in k) or (cat_lower in ["study", "flashcards"] and "STUDY" in k) or (cat_lower in ["diagnostics", "trust", "diag"] and "DIAGNOSTICS" in k)}
            if matched_cats:
                categories = matched_cats
            else:
                console.print(f"[yellow]Unknown category '{category_filter}'. Available categories: {', '.join(categories.keys())}[/yellow]")
                return

        output_lines = []
        for cat_name, cmds in categories.items():
            output_lines.append(f"[bold yellow]=== {cat_name} ===[/bold yellow]")
            for cmd, desc in cmds:
                output_lines.append(f"  [bold bright_cyan]{cmd:<38}[/bold bright_cyan] - [white]{desc}[/white]")
            output_lines.append("")

        output_lines.append("[dim]Tip: Use '/help <category>' (e.g. '/help trading' or '/help study') to view a specific category.[/dim]")
        
        title_str = f"[bold bright_cyan]JARVIS Commands Help ({cat_lower.upper() if cat_lower else 'ALL'})[/bold bright_cyan]"
        console.print(Panel("\n".join(output_lines), title=title_str, border_style="bright_cyan"))

    def handle_whoami(self) -> str:
        """Summarize user profile and stored facts"""
        profile = self.memory.get_profile()
        facts = self.memory.get_facts()
        
        lines = ["User Profile Summary:"]
        for k, v in profile.items():
            lines.append(f"- {k.replace('_', ' ').title()}: {v}")
            
        if facts:
            lines.append(f"\nStored Facts ({len(facts)} items):")
            for f in facts[:10]:
                lines.append(f"- [{f.get('category','general')}] {f['content']}")
                
        return "\n".join(lines)

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
            # Synchronize structured tool execution record into LLM context history
            self.api_client.add_message("user", user_input)
            self.api_client.add_message("assistant", f"[RECORDED TOOL EXECUTION RESULT]\nCommand: {user_input}\nResult: {tool_response}")
            try:
                confirm_prompt = (
                    f"The user requested: '{user_input}'.\n"
                    f"The tool executed and returned this exact result:\n{tool_response}\n\n"
                    "Relay this result to the user as JARVIS in 1-2 concise sentences. "
                    "You MUST include the exact file contents, paths, or data returned by the tool."
                )
                final_text = await self._get_ai_response(confirm_prompt)
                if final_text and final_text.strip():
                    return final_text
            except Exception:
                pass
            return tool_response or "Done, sir."

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
        
        if cmd_lower.startswith("/help"):
            parts = cmd_raw.split(maxsplit=1)
            cat = parts[1] if len(parts) > 1 else None
            self.show_help(cat)
            return f"Displaying help information{' for category ' + cat if cat else ''}, sir."
        elif cmd_lower in ["/whoami", "/recall"]:
            return self.handle_whoami()
        elif cmd_lower == "/diagnose":
            return await self.handle_diagnose_command()
        elif cmd_lower.startswith("/why"):
            return self.handle_why_command(cmd_raw)
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
        elif cmd_lower.startswith("/flashcard"):
            return await self.handle_flashcard_command(cmd_raw)
        elif cmd_lower == "/review":
            return await self.handle_review_command()
        elif cmd_lower.startswith("/deadline"):
            return await self.handle_deadline_command(cmd_raw)
        elif cmd_lower == "/deadlines":
            return self.show_deadlines()
        elif cmd_lower.startswith("/summarize"):
            return await self.handle_summarize_pdf_command(cmd_raw)
        elif cmd_lower.startswith("/explain-error"):
            return await self.handle_explain_error_command(cmd_raw)
        elif cmd_lower.startswith("/idea ") or cmd_lower == "/idea":
            return self.handle_idea_command(cmd_raw)
        elif cmd_lower.startswith("/ideas"):
            return self.handle_ideas_command(cmd_raw)
        elif cmd_lower.startswith("/meeting"):
            return await self.handle_meeting_command(cmd_raw)
        elif cmd_lower.startswith("/watch"):
            return self.handle_watch_command(cmd_raw)
        elif cmd_lower.startswith("/trade"):
            return self.handle_trade_command(cmd_raw)
        elif cmd_lower.startswith("/projects"):
            return await self.handle_projects_command(cmd_raw)
        elif cmd_lower.startswith("/tasks overdue") or cmd_lower == "/tasks overdue":
            return await self.handle_tasks_overdue_command()
        elif cmd_lower.startswith("/task"):
            return await self.handle_task_command(cmd_raw)
        elif cmd_lower.startswith("/decide"):
            return self.handle_decide_command(cmd_raw)
        elif cmd_lower.startswith("/note "):
            return self.handle_project_note_command(cmd_raw)
        elif cmd_lower.startswith("/timeline"):
            return self.handle_timeline_command(cmd_raw)
        elif cmd_lower.startswith("/milestone"):
            return self.handle_milestone_command(cmd_raw)
        elif cmd_lower.startswith("/protocol"):
            return await self.handle_protocol_command(cmd_raw)
        elif cmd_lower.startswith("/system"):
            parts = cmd_raw.split(maxsplit=1)
            sub = parts[1].lower() if len(parts) > 1 else ""
            if sub == "log":
                anomalies = self.proactive_monitor.system_monitor.get_recent_anomalies()
                if not anomalies:
                    return "No recent system resource anomalies recorded, sir."
                lines = ["=== Recent System Resource Anomalies ==="]
                for a in anomalies:
                    lines.append(f"[{a['timestamp']}] [{a['level'].upper()}] {a['message']}")
                return "\n".join(lines)
            else:
                snap = self.proactive_monitor.system_monitor.get_system_snapshot()
                lines = [
                    "=== Real-Time System Telemetry ===",
                    f"CPU Usage: {snap['cpu_pct']:.1f}%",
                    f"RAM Usage: {snap['ram_pct']:.1f}% ({snap['ram_used_gb']} GB / {snap['ram_total_gb']} GB)",
                ]
                if snap['gpu']:
                    gpu = snap['gpu']
                    lines.append(f"GPU ({gpu['name']}): {gpu['gpu_util_pct']:.1f}% Util | Temp: {gpu['temp_c']:.0f}°C | VRAM: {gpu['mem_used_mb']:.0f} MB / {gpu['mem_total_mb']:.0f} MB ({gpu['mem_util_pct']:.1f}%)")
                else:
                    lines.append("GPU: N/A (No NVIDIA GPU detected)")
                lines.append(f"Network Status: {'Online' if snap['network_online'] else 'Offline'}")
                lines.append("Drive Storage:")
                for d in snap['disks']:
                    warn_tag = " ⚠️ [LOW DISK SPACE]" if d.get('percent_used', 0) > 90.0 else ""
                    lines.append(f"  - {d['mountpoint']} {d['percent_used']}% used ({d['free_gb']} GB free / {d['total_gb']} GB total){warn_tag}")
                return "\n".join(lines)
        elif cmd_lower.startswith("/weather"):
            is_tomorrow = "tomorrow" in cmd_lower
            return self.proactive_monitor.weather_manager.format_weather_command(is_tomorrow=is_tomorrow)
        elif cmd_lower.startswith("/calendar"):
            parts = cmd_raw.split(maxsplit=1)
            sub = parts[1].lower() if len(parts) > 1 else "today"
            mode = "today"
            if "tomorrow" in sub:
                mode = "tomorrow"
            elif "next" in sub:
                mode = "next"
            return self.proactive_monitor.calendar_service.format_calendar_command(mode=mode)
        elif cmd_lower.startswith("/email"):
            parts = cmd_raw.split(maxsplit=2)
            sub = parts[1].lower() if len(parts) > 1 else ""
            if sub == "summary":
                return self.proactive_monitor.email_service.generate_email_summary_briefing()
            elif sub == "read":
                try:
                    idx = int(parts[2]) if len(parts) > 2 else 1
                except ValueError:
                    idx = 1
                return self.proactive_monitor.email_service.read_email_body_by_index(idx)
            else:
                return self.proactive_monitor.email_service.format_unread_list()
        elif cmd_lower.startswith("/search"):
            parts = cmd_raw.split(maxsplit=1)
            query = parts[1].strip() if len(parts) > 1 else ""
            if not query:
                return "Usage: /search <query>"
            if query.lower().startswith("ddg "):
                query = query[4:].strip()
            
            res = await self.tools.execute_tool("duckduckgo_search", query=query)
            try:
                if hasattr(self.proactive_monitor, "tts") and self.proactive_monitor.tts:
                    speak_msg = f"Sir, I have retrieved search results for '{query}'."
                    await self.proactive_monitor.tts.speak(speak_msg)
            except Exception:
                pass
            return res
        elif cmd_lower.startswith(("/open", "/launch")):
            parts = cmd_raw.split(maxsplit=1)
            app = parts[1].strip() if len(parts) > 1 else ""
            if not app:
                return "Usage: /open <app_name>"
            return await self.tools.execute_tool("open_application", app_name=app)
        elif cmd_lower.startswith(("/close", "/kill")):
            parts = cmd_raw.split(maxsplit=1)
            app = parts[1].strip() if len(parts) > 1 else ""
            if not app:
                return "Usage: /close <app_name>"
            confirm = "confirm" in cmd_lower or "force" in cmd_lower
            clean_app = app.replace("confirm", "").replace("force", "").strip()
            return await self.tools.execute_tool("close_application", app_name=clean_app or app, confirm=confirm)
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

    def parse_reminder_time(self, user_input: str) -> tuple[str, datetime]:
        """
        Parse reminder text and compute real due_at datetime.
        Supports seconds, minutes, hours, days (e.g. 'in 15 seconds', 'in 2 mins', 'in 1 hour', 'in 30s').
        """
        from datetime import datetime, timedelta
        now = datetime.now()
        clean_input = user_input.strip()
        
        # Duration regex: e.g. "in 15 seconds", "in 2 minutes", "in 1 hour", "in 30 sec", "in 45s"
        match = re.search(r'\bin\s+(\d+)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d)\b', clean_input, re.I)
        
        seconds_to_add = 300  # Default 5 minutes if no duration is specified
        
        if match:
            amount = int(match.group(1))
            unit = match.group(2).lower()
            
            if unit in ["s", "sec", "secs", "second", "seconds"]:
                seconds_to_add = amount
            elif unit in ["m", "min", "mins", "minute", "minutes"]:
                seconds_to_add = amount * 60
            elif unit in ["h", "hr", "hrs", "hour", "hours"]:
                seconds_to_add = amount * 3600
            elif unit in ["d", "day", "days"]:
                seconds_to_add = amount * 86400

            # Remove duration specifier from text
            reminder_text = re.sub(r'\bin\s+\d+\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d)\b', '', clean_input, flags=re.I).strip()
        else:
            reminder_text = clean_input
            
        # Remove common prefixes
        reminder_text = re.sub(r'^(remind\s+(me\s+)?(to\s+)?|set\s+a\s+reminder\s+(to\s+)?|add\s+reminder\s+(to\s+)?)', '', reminder_text, flags=re.I).strip()
        if not reminder_text:
            reminder_text = "General Reminder"
            
        due_at = now + timedelta(seconds=seconds_to_add)
        return reminder_text, due_at

    def get_pending_reminders_summary(self) -> str:
        """Query pending database reminders and format exact status summary"""
        from datetime import datetime
        reminders = self.memory.get_reminders()
        pending = [r for r in reminders if not r["completed"]]
        
        if not pending:
            return "No pending reminders in database, sir."
            
        now = datetime.now()
        lines = ["Pending Reminders:"]
        for r in pending:
            due_date_str = r.get("due_date")
            if due_date_str:
                try:
                    due_dt = datetime.fromisoformat(due_date_str)
                    diff = (due_dt - now).total_seconds()
                    due_time_fmt = due_dt.strftime("%H:%M:%S")
                    if diff > 0:
                        lines.append(f"- '{r['text']}' is pending, due at {due_time_fmt} (in {int(diff)} seconds).")
                    else:
                        lines.append(f"- '{r['text']}' is pending, due at {due_time_fmt} (overdue).")
                except ValueError:
                    lines.append(f"- '{r['text']}' is pending.")
            else:
                lines.append(f"- '{r['text']}' is pending.")
                
        return "\n".join(lines)

    async def handle_flashcard_command(self, cmd_raw: str) -> str:
        """Handle /flashcard [add|from-file] commands"""
        parts = cmd_raw.strip().split(maxsplit=2)
        if len(parts) < 2:
            return "Usage: /flashcard add \"question\" \"answer\" OR /flashcard from-file <path>"
        
        subcmd = parts[1].lower()
        if subcmd == "add" and len(parts) > 2:
            body = parts[2].strip()
            q, a = "", ""
            if "|" in body:
                q, a = body.split("|", 1)
            elif '"' in body:
                matches = re.findall(r'"([^"]*)"', body)
                if len(matches) >= 2:
                    q, a = matches[0], matches[1]
                else:
                    return 'Usage: /flashcard add "question" "answer"'
            else:
                return 'Usage: /flashcard add "question" "answer" or /flashcard add Q | A'
            
            card = self.memory.add_flashcard(q, a)
            return f"Flashcard added (ID: {card['id']}):\nQ: {card['question']}\nA: {card['answer']}"
        
        elif subcmd == "from-file" and len(parts) > 2:
            filepath = parts[2].strip().strip('"\'')
            path = Path(filepath)
            if not path.exists():
                return f"Error: File '{filepath}' not found."
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            if not content.strip():
                return f"Error: File '{filepath}' is empty."
            
            prompt = f"Extract all important Q&A flashcard pairs from the following text notes. Return ONLY a valid JSON array of objects with keys 'question' and 'answer':\n\n{content[:4000]}"
            res_json = ""
            async for chunk in self.api_client.chat_stream(prompt):
                res_json += chunk
            
            import json
            try:
                start_idx = res_json.find('[')
                end_idx = res_json.rfind(']')
                if start_idx != -1 and end_idx != -1:
                    cards = json.loads(res_json[start_idx:end_idx+1])
                    added_count = 0
                    for c in cards:
                        if "question" in c and "answer" in c:
                            self.memory.add_flashcard(c["question"], c["answer"])
                            added_count += 1
                    return f"Extracted and stored {added_count} flashcards into SQLite database from '{filepath}'."
            except Exception as e:
                return f"Failed to parse extracted JSON flashcards: {e}\nRaw output: {res_json[:300]}"
            return "Could not extract flashcards from notes file."
            
        return "Usage: /flashcard add \"question\" \"answer\" OR /flashcard from-file <path>"

    async def handle_review_command(self) -> str:
        """Handle /review interactive quiz mode"""
        due_cards = self.memory.get_due_flashcards()
        if not due_cards:
            return "No flashcards due for review right now, sir! Great job!"
        
        card = due_cards[0]
        console.print(f"\n[bold cyan]📚 FLASHCARD QUIZ (ID: {card['id']})[/bold cyan]")
        console.print(f"[bold white]Q: {card['question']}[/bold white]\n")
        await asyncio.to_thread(Prompt.ask, "Press Enter to reveal answer")
        console.print(f"[bold green]A: {card['answer']}[/bold green]\n")
        
        is_correct = await asyncio.to_thread(Confirm.ask, "Did you answer correctly?")
        self.memory.update_flashcard_review(card['id'], is_correct)
        
        next_interval = (card.get("interval_days", 1) or 1) * 2 if is_correct else 1
        status_msg = f"[green]Correct! Interval pushed to {next_interval} days.[/green]" if is_correct else "[yellow]Incorrect. Reset to 1 day interval.[/yellow]"
        console.print(status_msg)
        return f"Reviewed Flashcard #{card['id']}. {len(due_cards) - 1} remaining due."

    async def handle_deadline_command(self, cmd_raw: str) -> str:
        """Handle /deadline add "name" <date> or /deadlines"""
        parts = cmd_raw.strip().split(maxsplit=2)
        if len(parts) < 2:
            return "Usage: /deadline add \"assignment\" <date>"
        
        subcmd = parts[1].lower()
        if subcmd == "add" and len(parts) > 2:
            body = parts[2].strip()
            name = ""
            date_str = ""
            if '"' in body:
                matches = re.findall(r'"([^"]*)"', body)
                if matches:
                    name = matches[0]
                    date_str = body.replace(f'"{name}"', '').strip()
            if not name:
                parts_body = body.split(maxsplit=1)
                name = parts_body[0]
                date_str = parts_body[1] if len(parts_body) > 1 else ""
            
            _, due_at = self.parse_reminder_time(f"remind me in {date_str} to {name}" if date_str else name)
            deadline = self.memory.add_deadline(name, due_at.isoformat())
            return f"Deadline added: '{name}' due at {due_at.strftime('%Y-%m-%d %H:%M:%S')}."
            
        return "Usage: /deadline add \"assignment\" <date>"

    def show_deadlines(self) -> str:
        """Display pending deadlines with remaining time"""
        deadlines = self.memory.get_pending_deadlines()
        if not deadlines:
            return "No pending deadlines, sir."
        
        now = datetime.now()
        table = Table(title="[bold cyan]Pending Deadlines[/bold cyan]")
        table.add_column("ID", style="cyan")
        table.add_column("Assignment / Event", style="white")
        table.add_column("Due Datetime", style="yellow")
        table.add_column("Time Remaining", style="green")
        
        lines = ["Pending Deadlines:"]
        for d in deadlines:
            due_dt = datetime.fromisoformat(d["due_date"])
            diff = (due_dt - now).total_seconds()
            hours = int(diff / 3600)
            days = int(hours / 24)
            rem_str = f"{days} days ({hours % 24}h)" if days > 0 else f"{hours} hours ({int((diff % 3600)/60)}m)"
            if diff < 0:
                rem_str = "[red]OVERDUE[/red]"
            table.add_row(str(d["id"]), d["name"], due_dt.strftime("%Y-%m-%d %H:%M"), rem_str)
            lines.append(f"- '{d['name']}' due at {due_dt.strftime('%Y-%m-%d %H:%M')} ({rem_str})")
            
        console.print(table)
        return "\n".join(lines)

    async def handle_summarize_pdf_command(self, cmd_raw: str) -> str:
        """Handle /summarize <path.pdf>"""
        parts = cmd_raw.strip().split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /summarize <path.pdf>"
        
        filepath = parts[1].strip().strip('"\'')
        extracted_text = await self.tools.execute_tool("summarize_pdf", filepath=filepath)
        if extracted_text.startswith("Error:"):
            return extracted_text
        
        prompt = f"You are an academic paper summarizer. Summarize the following REAL extracted paper text into structured bullet points with sections: 1. Core Claim / Objective, 2. Methodology / Approach, 3. Key Results / Findings:\n\n{extracted_text[:4000]}"
        
        summary = ""
        async for chunk in self.api_client.chat_stream(prompt):
            summary += chunk
        return summary

    async def handle_explain_error_command(self, cmd_raw: str) -> str:
        """Handle /explain-error [error_text] command"""
        parts = cmd_raw.strip().split(maxsplit=1)
        error_text = parts[1].strip() if len(parts) > 1 else getattr(self, "last_failed_command_output", "")
        
        if not error_text:
            return "Please provide error text to explain (e.g. /explain-error <pasted error>) or run a command first that produces an error."
        
        prompt = f"Explain the following REAL software error in plain language, identify the likely root cause, and provide clear step-by-step fix suggestions:\n\n{error_text[:4000]}"
        explanation = ""
        async for chunk in self.api_client.chat_stream(prompt):
            explanation += chunk
        return explanation

    def handle_idea_command(self, cmd_raw: str) -> str:
        """Handle /idea <text> command"""
        parts = cmd_raw.strip().split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            return "Usage: /idea <your idea or decision text>"
        
        idea_text = parts[1].strip()
        idea = self.memory.add_idea(idea_text)
        return f"Idea logged (ID: {idea['id']}): '{idea['title']}'."

    def handle_ideas_command(self, cmd_raw: str) -> str:
        """Handle /ideas [list|search <keyword>] command"""
        parts = cmd_raw.strip().split(maxsplit=2)
        subcmd = parts[1].lower() if len(parts) > 1 else "list"
        
        if subcmd in ["list", "all"]:
            ideas = self.memory.get_ideas()
            if not ideas:
                return "No stored ideas found in database, sir."
            table = Table(title="[bold cyan]Idea & Decision Journal[/bold cyan]")
            table.add_column("ID", style="cyan")
            table.add_column("Title", style="white")
            table.add_column("Created At", style="yellow")
            for i in ideas:
                table.add_row(str(i["id"]), i["title"], i.get("created_at", "")[:16])
            console.print(table)
            return f"Found {len(ideas)} logged ideas."
            
        elif subcmd in ["search", "find"] and len(parts) > 2:
            kw = parts[2].strip()
            results = self.memory.search_ideas(kw)
            if not results:
                return f"No ideas matching '{kw}' found."
            lines = [f"Search Results for '{kw}':"]
            for r in results:
                lines.append(f"- ID {r['id']}: [{r.get('created_at','')[:10]}] {r['title']}\n  {r['content']}")
            return "\n".join(lines)
            
        return "Usage: /ideas list OR /ideas search <keyword>"

    async def handle_meeting_command(self, cmd_raw: str) -> str:
        """Handle /meeting prep <person/topic>"""
        parts = cmd_raw.strip().split(maxsplit=2)
        if len(parts) < 3 or parts[1].lower() != "prep":
            return "Usage: /meeting prep <person/topic>"
            
        target = parts[2].strip()
        # Query stored facts, notes, profile, ideas
        facts = self.memory.search_facts(target)
        notes = [n for n in self.memory.get_notes() if target.lower() in n.get("text", "").lower()]
        ideas = self.memory.search_ideas(target)
        
        context_parts = []
        if facts:
            context_parts.append("Stored Facts:\n" + "\n".join(f"- {f['content']}" for f in facts))
        if notes:
            context_parts.append("Stored Notes:\n" + "\n".join(f"- {n['text']}" for n in notes))
        if ideas:
            context_parts.append("Stored Ideas:\n" + "\n".join(f"- {i['title']}: {i['content']}" for i in ideas))
            
        if not context_parts:
            return f"No stored facts, notes, or ideas found for '{target}'. Add facts with 'save fact:' or notes before meeting prep."
            
        raw_briefing = "\n\n".join(context_parts)
        prompt = f"You are JARVIS preparing a meeting briefing for '{target}'. Synthesize the following REAL stored memory facts into a structured briefing with sections: 1. Background & Context, 2. Key Facts / Notes, 3. Related Ideas / Action Items. Base your briefing ONLY on the provided stored data:\n\n{raw_briefing}"
        
        briefing = ""
        async for chunk in self.api_client.chat_stream(prompt):
            briefing += chunk
        return briefing

    def handle_watch_command(self, cmd_raw: str) -> str:
        """Handle /watch <ticker> <above|below> <price>"""
        parts = cmd_raw.strip().split()
        if len(parts) < 4:
            return "Usage: /watch <ticker> <above|below> <target_price> (e.g. /watch AAPL above 200)"
        
        ticker = parts[1].upper()
        condition = parts[2].lower()
        if condition not in ["above", "below", ">", "<", ">=", "<="]:
            return "Error: Condition must be 'above' or 'below'"
        try:
            target_price = float(parts[3])
        except ValueError:
            return "Error: Target price must be a valid number"
            
        watch = self.memory.add_price_watch(ticker, condition, target_price)
        return f"Price watch set for {ticker} when price moves {condition} ${target_price:.2f} (Watch ID: {watch['id']})."

    def handle_trade_command(self, cmd_raw: str) -> str:
        """Handle /trade [log|review] commands"""
        parts = cmd_raw.strip().split(maxsplit=2)
        if len(parts) < 2:
            return "Usage: /trade log <ticker> <buy/sell> <price> <qty> reason: <text> OR /trade review [ticker]"
            
        subcmd = parts[1].lower()
        if subcmd == "log" and len(parts) > 2:
            body = parts[2].strip()
            reason = ""
            if "reason:" in body.lower():
                r_idx = body.lower().index("reason:")
                reason = body[r_idx + 7:].strip()
                body = body[:r_idx].strip()
                
            tokens = body.split()
            if len(tokens) < 4:
                return "Usage: /trade log <ticker> <BUY/SELL> <price> <quantity> [reason: text]"
                
            ticker = tokens[0].upper()
            action = tokens[1].upper()
            if action not in ["BUY", "SELL"]:
                return "Error: Action must be BUY or SELL"
            try:
                price = float(tokens[2])
                qty = float(tokens[3])
            except ValueError:
                return "Error: Price and quantity must be valid numbers"
                
            trade = self.memory.add_trade(ticker, action, price, qty, reason)
            return f"Trade logged (ID: {trade['id']}): {action} {qty} {ticker} @ ${price:.2f}."
            
        elif subcmd in ["review", "list"]:
            ticker_filter = parts[2].strip() if len(parts) > 2 else None
            trades = self.memory.get_trades(ticker_filter)
            if not trades:
                return f"No logged trades found{' for ' + ticker_filter if ticker_filter else ''}, sir."
                
            table = Table(title=f"[bold cyan]Trade Journal{' (' + ticker_filter.upper() + ')' if ticker_filter else ''}[/bold cyan]")
            table.add_column("ID", style="cyan")
            table.add_column("Timestamp", style="yellow")
            table.add_column("Action", style="green")
            table.add_column("Ticker", style="white")
            table.add_column("Price", style="white")
            table.add_column("Qty", style="white")
            table.add_column("Reason", style="dim white")
            
            for t in trades:
                act_str = f"[bold green]BUY[/bold green]" if t["action"] == "BUY" else f"[bold red]SELL[/bold red]"
                table.add_row(
                    str(t["id"]),
                    t.get("timestamp", "")[:16],
                    act_str,
                    t["ticker"],
                    f"${t['price']:.2f}",
                    str(t["quantity"]),
                    t.get("reason", "")
                )
            console.print(table)
            return f"Retrieved {len(trades)} trade journal entries."
            
        return "Usage: /trade log <ticker> <BUY/SELL> <price> <qty> [reason: text] OR /trade review [ticker]"

    async def handle_diagnose_command(self) -> str:
        """Perform live self-diagnostic checks of all JARVIS subsystems"""
        table = Table(title="[bold cyan]JARVIS Subsystem Live Diagnostics[/bold cyan]")
        table.add_column("Subsystem", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Detail Message", style="white")
        
        # 1. Database
        db_ok, db_msg = self.memory.test_connection()
        db_status = "[bold green]✓ OK[/bold green]" if db_ok else "[bold red]✗ FAILED[/bold red]"
        table.add_row("SQLite Database", db_status, db_msg)
        
        # 2. NIM API
        api_ok, api_msg, _ = await self.api_client.test_connection()
        api_status = "[bold green]✓ OK[/bold green]" if api_ok else "[bold red]✗ FAILED[/bold red]"
        table.add_row("NVIDIA NIM API", api_status, api_msg)
        
        # 3. Audio/TTS
        from jarvis.voice import test_tts, test_mic
        tts_ok, tts_msg = await test_tts()
        tts_status = "[bold green]✓ OK[/bold green]" if tts_ok else "[bold red]✗ FAILED[/bold red]"
        table.add_row("Edge-TTS Audio", tts_status, tts_msg)
        
        # 4. Audio Input Device (Mic)
        mic_ok, mic_msg = test_mic()
        mic_status = "[bold green]✓ OK[/bold green]" if mic_ok else "[bold red]✗ FAILED[/bold red]"
        table.add_row("Microphone Input", mic_status, mic_msg)
        
        # 5. Background Threads (ProactiveMonitor)
        pm_alive = self.proactive_monitor.thread.is_alive() if (hasattr(self.proactive_monitor, 'thread') and self.proactive_monitor.thread) else False
        last_ts = getattr(self.proactive_monitor, 'last_check_timestamp', None)
        if pm_alive and last_ts:
            seconds_ago = (datetime.now() - last_ts).total_seconds()
            if seconds_ago <= 120:
                pm_ok = True
                pm_msg = f"Thread active (last checked {seconds_ago:.0f}s ago)"
            else:
                pm_ok = False
                pm_msg = f"Thread hung (last checked {seconds_ago:.0f}s ago)"
        elif pm_alive:
            pm_ok = True
            pm_msg = "Thread active (starting up)"
        else:
            pm_ok = False
            pm_msg = "Thread inactive / stopped"
            
        pm_status = "[bold green]✓ OK[/bold green]" if pm_ok else "[bold red]✗ FAILED[/bold red]"
        table.add_row("Proactive Monitor", pm_status, pm_msg)
        
        # 6. System Resource Telemetry
        sys_snap = self.proactive_monitor.system_monitor.get_system_snapshot()
        sys_msg = f"CPU: {sys_snap['cpu_pct']:.1f}% | RAM: {sys_snap['ram_pct']:.1f}% | GPU: {'Online' if sys_snap['gpu'] else 'N/A'} | Network: {'Online' if sys_snap['network_online'] else 'Offline'}"
        table.add_row("System Resource Monitor", "[bold green]✓ OK[/bold green]", sys_msg)

        # 7. Weather API Status
        weather_ok = self.proactive_monitor.weather_manager._is_configured()
        weather_msg = f"City: {self.proactive_monitor.weather_manager.city} ({self.proactive_monitor.weather_manager.country}) | API Key configured" if weather_ok else "OPENWEATHER_API_KEY missing/unconfigured in .env"
        weather_status = "[bold green]✓ OK[/bold green]" if weather_ok else "[bold yellow]⚠ UNCONFIGURED[/bold yellow]"
        table.add_row("Weather API", weather_status, weather_msg)

        # 8. Google OAuth2 (Calendar & Gmail)
        g_auth_ok = self.proactive_monitor.google_auth.is_authenticated()
        g_msg = "Authenticated (token valid)" if g_auth_ok else "Not authenticated (run Google OAuth setup or check credentials.json)"
        g_status = "[bold green]✓ OK[/bold green]" if g_auth_ok else "[bold yellow]⚠ UNAUTHENTICATED[/bold yellow]"
        table.add_row("Google Sync (Calendar/Gmail)", g_status, g_msg)

        console.print(table)
        return "Self-diagnostic check complete, sir."

    def handle_why_command(self, cmd_raw: str) -> str:
        """Explain the tool execution details for recent response"""
        parts = cmd_raw.strip().split()
        idx = 0
        if len(parts) > 1:
            arg = parts[-1]
            if arg.isdigit():
                idx = max(0, int(arg) - 1)
                
        transactions = getattr(self.tools, 'last_transactions', [])
        if not transactions:
            return "That was a direct response, no tools were used."
            
        if idx >= len(transactions):
            return f"Requested tool transaction #{idx + 1} not found. Only {len(transactions)} tool call(s) logged in session."
            
        tx = transactions[idx]
        kwargs_str = json.dumps(tx['kwargs'], indent=2)
        res_str = tx['result'][:1500]
        
        explanation_text = (
            f"[bold cyan]Tool Called:[/bold cyan] {tx['tool']}\n"
            f"[bold cyan]Timestamp:[/bold cyan] {tx['timestamp']}\n"
            f"[bold cyan]Exact Arguments:[/bold cyan]\n{kwargs_str}\n\n"
            f"[bold cyan]Raw Execution Result:[/bold cyan]\n{res_str}\n\n"
            f"[bold yellow]Rationale:[/bold yellow] Executed tool '{tx['tool']}' with provided arguments and supplied raw result to response context."
        )
        
        title = f"[bold cyan]Action Explanation (/why #{idx + 1})[/bold cyan]"
        console.print(Panel(explanation_text, title=title, border_style="cyan"))
        return f"Displayed action explanation for tool transaction #{idx + 1} ({tx['tool']})."

    async def handle_projects_command(self, cmd_raw: str) -> str:
        parts = cmd_raw.split(maxsplit=1)
        sub = parts[1].strip() if len(parts) > 1 else ""

        if not sub:
            return await self.tools.execute_tool("project_tool", action="list", status="active")
        elif sub.lower() == "all":
            return await self.tools.execute_tool("project_tool", action="list")
        elif sub.lower() == "add":
            return await self.handle_project_add_guided()
        else:
            return await self.tools.execute_tool("project_tool", action="get", name_or_id=sub)

    async def handle_project_add_guided(self) -> str:
        console.print("[bold cyan]=== Guided Project Creation ===[/bold cyan]")
        from rich.prompt import Prompt
        import asyncio

        name = await asyncio.to_thread(Prompt.ask, "Project Name")
        if not name:
            return "Project creation cancelled: Name cannot be empty."

        desc = await asyncio.to_thread(Prompt.ask, "Description (optional)", default="")
        category = await asyncio.to_thread(Prompt.ask, "Category (personal/client/startup/study/trading/other)", default="personal")
        tech_stack = await asyncio.to_thread(Prompt.ask, "Tech Stack (e.g. Python, React, SQLite)", default="")
        deadline = await asyncio.to_thread(Prompt.ask, "Deadline (YYYY-MM-DD, optional)", default="")
        repo_url = await asyncio.to_thread(Prompt.ask, "Repo URL (optional)", default="")
        priority_str = await asyncio.to_thread(Prompt.ask, "Priority (1-5)", default="3")

        try:
            priority = int(priority_str)
        except ValueError:
            priority = 3

        p_id = self.project_manager.create_project(
            name=name,
            description=desc,
            category=category,
            tech_stack=tech_stack,
            deadline=deadline,
            repo_url=repo_url,
            priority=priority
        )

        if p_id:
            msg = f"Project '{name}' successfully created with ID {p_id}, sir."
            try:
                if hasattr(self.proactive_monitor, "tts") and self.proactive_monitor.tts:
                    await self.proactive_monitor.tts.speak(msg)
            except Exception:
                pass
            return msg
        else:
            return f"Failed to create project '{name}'. A project with that name already exists."

    async def handle_task_command(self, cmd_raw: str) -> str:
        parts = cmd_raw.split(maxsplit=3)
        if len(parts) < 2:
            return "Usage: /task add <project> <task> | /task done <project> <task> | /task list <project>"

        sub = parts[1].lower()
        if sub == "list" and len(parts) >= 3:
            project_name = parts[2]
            p = self.project_manager.get_project(project_name)
            if not p:
                return f"Project '{project_name}' not found in database."
            tasks = p.get("tasks", [])
            if not tasks:
                return f"No tasks found for project '{p['name']}'."
            lines = [f"=== Tasks for {p['name']} ==="]
            for t in tasks:
                due = f" (Due: {t['due_date']})" if t.get("due_date") else ""
                lines.append(f"  - [{t['status'].upper()}] #{t['id']} {t['title']}{due}")
            return "\n".join(lines)

        elif sub == "add" and len(parts) >= 4:
            project_name = parts[2]
            task_title = parts[3]
            p_id = self.project_manager.resolve_project_id(project_name)
            if not p_id:
                return f"Project '{project_name}' not found in database."
            t_id = self.project_manager.add_task(project_id=p_id, title=task_title)
            return f"Added task '{task_title}' to project '{project_name}' (Task #{t_id})."

        elif sub == "done" and len(parts) >= 4:
            project_name = parts[2]
            task_query = parts[3]
            p_id = self.project_manager.resolve_project_id(project_name)
            if not p_id:
                return f"Project '{project_name}' not found in database."
            task = self.project_manager.find_task_by_title(p_id, task_query)
            if not task:
                if task_query.isdigit():
                    t_id = int(task_query)
                else:
                    return f"Task matching '{task_query}' not found in project '{project_name}'."
            else:
                t_id = task["id"]

            ok = self.project_manager.update_task(task_id=t_id, status="done")
            if ok:
                return f"Marked task #{t_id} as DONE in project '{project_name}', sir."
            return f"Failed to update task #{t_id}."

        return "Usage: /task add <project> <task> | /task done <project> <task> | /task list <project>"

    async def handle_tasks_overdue_command(self) -> str:
        return await self.tools.execute_tool("project_tool", action="overdue")

    def handle_decide_command(self, cmd_raw: str) -> str:
        parts = cmd_raw.split(maxsplit=2)
        if len(parts) < 3:
            return "Usage: /decide <project> <decision text>"
        project_name = parts[1]
        decision_text = parts[2]
        p_id = self.project_manager.resolve_project_id(project_name)
        if not p_id:
            return f"Project '{project_name}' not found in database."
        dec_id = self.project_manager.add_decision(project_id=p_id, decision=decision_text)
        return f"Logged decision for project '{project_name}': '{decision_text}' (ID #{dec_id})."

    def handle_project_note_command(self, cmd_raw: str) -> str:
        parts = cmd_raw.split(maxsplit=2)
        if len(parts) < 3:
            return "Usage: /note <project> <note text>"
        project_name = parts[1]
        note_text = parts[2]
        p_id = self.project_manager.resolve_project_id(project_name)
        if not p_id:
            return f"Project '{project_name}' not found in database."
        n_id = self.project_manager.add_note(project_id=p_id, content=note_text)
        return f"Added note to project '{project_name}': '{note_text}' (ID #{n_id})."

    def handle_timeline_command(self, cmd_raw: str) -> str:
        parts = cmd_raw.split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /timeline <project>"
        project_name = parts[1]
        p_id = self.project_manager.resolve_project_id(project_name)
        if not p_id:
            return f"Project '{project_name}' not found in database."
        timeline = self.project_manager.get_project_timeline(p_id)
        if not timeline:
            return f"No timeline events recorded for project '{project_name}'."
        lines = [f"=== Timeline for {project_name} ==="]
        for tm in timeline:
            lines.append(f"• [{tm.get('date', 'N/A')}] [{tm.get('type', 'update').upper()}] {tm['event']}")
        return "\n".join(lines)

    def handle_milestone_command(self, cmd_raw: str) -> str:
        parts = cmd_raw.split(maxsplit=2)
        if len(parts) < 3:
            return "Usage: /milestone <project> <event text>"
        project_name = parts[1]
        event_text = parts[2]
        p_id = self.project_manager.resolve_project_id(project_name)
        if not p_id:
            return f"Project '{project_name}' not found in database."
        ev_id = self.project_manager.add_timeline_event(project_id=p_id, event=event_text, type_str="milestone")
        return f"Added milestone to project '{project_name}': '{event_text}' (ID #{ev_id})."

    async def _check_tool_commands(self, user_input: str) -> Optional[str]:
        """Check if input matches a tool command or protocol trigger"""
        input_lower = user_input.lower()

        # Natural Language Project Triggers
        if any(phrase in input_lower for phrase in ["what projects am i working on", "what projects am i working", "my active projects", "list active projects", "what projects do i have"]):
            return await self.tools.execute_tool("project_tool", action="list", status="active")

        if "briefing on " in input_lower or "briefing for " in input_lower:
            m = re.search(r'(give\s+me\s+a\s+full\s+)?briefing\s+(on|for)\s+(.+)', user_input, re.I)
            if m:
                p_name = m.group(3).strip().rstrip('?.!')
                return await self.tools.execute_tool("project_tool", action="get", name_or_id=p_name)

        if "overdue" in input_lower and ("task" in input_lower or "tasks" in input_lower):
            return await self.tools.execute_tool("project_tool", action="overdue")

        if "add" in input_lower and "task" in input_lower:
            m1 = re.search(r'add\s+(a\s+)?task\s+to\s+([^:]+):\s*(.+)', user_input, re.I)
            if m1:
                p_name = m1.group(2).strip()
                t_desc = m1.group(3).strip()
                return await self.handle_task_command(f"/task add {p_name} {t_desc}")
            m2 = re.search(r'add\s+(a\s+)?task\s+to\s+(\S+)\s+(.+)', user_input, re.I)
            if m2:
                p_name = m2.group(2).strip()
                t_desc = m2.group(3).strip()
                return await self.handle_task_command(f"/task add {p_name} {t_desc}")

        if "mark" in input_lower and ("done" in input_lower or "completed" in input_lower) and "task" in input_lower:
            m = re.search(r'mark\s+(the\s+)?task\s+[\'"]?([^\'"]+)[\'"]?\s+as\s+(done|completed)\s+in\s+(.+)', user_input, re.I)
            if not m:
                m = re.search(r'mark\s+[\'"]?([^\'"]+)[\'"]?\s+as\s+(done|completed)\s+in\s+(.+)', user_input, re.I)
            if m:
                t_title = m.group(2 if m.lastindex >= 4 else 1).strip()
                p_name = m.group(4 if m.lastindex >= 4 else 3).strip()
                return await self.handle_task_command(f"/task done {p_name} {t_title}")

        if input_lower.startswith("create a new project called ") or input_lower.startswith("create a project called ") or input_lower.startswith("create project "):
            m = re.search(r'create\s+(a\s+)?(new\s+)?project\s+(called\s+|named\s+)?([a-zA-Z0-9_\-\s]+)', user_input, re.I)
            if m:
                p_name = m.group(4).strip().rstrip('?.!')
                p_id = self.project_manager.create_project(name=p_name)
                if p_id:
                    msg = f"Created new project '{p_name}' (ID #{p_id}), sir. You can add tasks, notes, or details anytime."
                    try:
                        if hasattr(self.proactive_monitor, "tts") and self.proactive_monitor.tts:
                            await self.proactive_monitor.tts.speak(msg)
                    except Exception:
                        pass
                    return msg
                else:
                    return f"Project '{p_name}' already exists in database."

        if "add" in input_lower and "note" in input_lower and "to" in input_lower:
            m = re.search(r'add\s+(a\s+)?note\s+to\s+([^:]+):\s*(.+)', user_input, re.I)
            if m:
                p_name = m.group(2).strip()
                n_text = m.group(3).strip()
                return self.handle_project_note_command(f"/note {p_name} {n_text}")

        if "we decided to " in input_lower:
            m = re.search(r'we\s+decided\s+to\s+(.+?)\s+because\s+(.+)', user_input, re.I)
            if m:
                dec_text = "We decided to " + m.group(1).strip()
                reason_text = m.group(2).strip()
                active = self.project_manager.get_active_projects_summary()
                if active:
                    target_p = active[0]
                    d_id = self.project_manager.add_decision(project_id=target_p["id"], decision=dec_text, reasoning=reason_text)
                    return f"Recorded decision for project '{target_p['name']}': {dec_text} (Reasoning: {reason_text})."

        if input_lower.endswith(" is done") or "mark project " in input_lower:
            m = re.search(r'(mark\s+project\s+)?([a-zA-Z0-9_\-\s]+)\s+is\s+done', user_input, re.I)
            if not m:
                m = re.search(r'mark\s+project\s+([a-zA-Z0-9_\-\s]+)\s+as\s+completed', user_input, re.I)
            if m:
                p_name = m.group(2 if m.lastindex >= 2 else 1).strip().rstrip('?.!')
                ok = self.project_manager.complete_project(p_name)
                if ok:
                    msg = f"Project '{p_name}' has been marked as completed, sir. Outstanding work."
                    try:
                        if hasattr(self.proactive_monitor, "tts") and self.proactive_monitor.tts:
                            await self.proactive_monitor.tts.speak(msg)
                    except Exception:
                        pass
                    return msg
        
        # Git Status Natural Language Matching
        if "git status" in input_lower or "what's my git status" in input_lower or "what branch am i on" in input_lower:
            result = await self.tools.execute_tool("git_status", directory=".")
            self.memory.log_task("Check git status", "completed")
            return result
        
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
                    
                    result = await self.tools.execute_tool("open_application", app_name=target)
                    self.memory.log_task(f"Open application {target}", "completed")
                    return result

        # Close Application
        for prefix in ["close ", "kill ", "stop ", "exit ", "terminate "]:
            if input_lower.startswith(prefix):
                target = user_input[len(prefix):].strip()
                target_lower = target.lower()
                
                if not ("folder" in target_lower or "directory" in target_lower or "file" in target_lower or "server" in target_lower):
                    confirm = "confirm" in input_lower or "yes" in input_lower or "force" in input_lower
                    clean_target = re.sub(r'^(confirm|yes|force)\s+', '', target, flags=re.I).strip()
                    result = await self.tools.execute_tool("close_application", app_name=clean_target or target, confirm=confirm)
                    self.memory.log_task(f"Close application {target}", "completed")
                    return result

        # Web Search / Browse URL / DuckDuckGo Search
        if any(kw in input_lower for kw in ["duckduckgo", "ddg", "search web for", "web search for"]):
            for prefix in ["search duckduckgo for", "duckduckgo search for", "search ddg for", "ddg search for", "search web for", "web search for", "duckduckgo", "ddg"]:
                if prefix in input_lower:
                    query = user_input[input_lower.index(prefix) + len(prefix):].strip().lstrip("for").strip()
                    if query:
                        result = await self.tools.execute_tool("duckduckgo_search", query=query)
                        self.memory.log_task(f"DuckDuckGo Search {query}", "completed")
                        try:
                            if hasattr(self.proactive_monitor, "tts") and self.proactive_monitor.tts:
                                await self.proactive_monitor.tts.speak(f"Sir, retrieved DuckDuckGo search results for '{query}'.")
                        except Exception:
                            pass
                        return result

        if "browse to" in input_lower or "search google for" in input_lower:
            for prefix in ["browse to", "search google for"]:
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
        elif any(kw in input_lower for kw in ["read", "cat", "view", "show contents of", "what is in", "what's in"]):
            filename = re.sub(r'^(can\s+you\s+)?(please\s+)?(read|cat|view|show\s+contents\s+of|what\s+is\s+in|what\'s\s+in|display)\s+(the\s+)?(contents\s+of\s+)?(file\s+)?', '', user_input, flags=re.I).strip().rstrip('?.!')
            if filename and len(filename.split()) <= 3:
                resolved_p = Path(filename).resolve()
                res_warn = f"⚠️ [PATH RESOLUTION] Resolving '{filename}' to '{resolved_p}' — proceeding.\n"
                result = await self.tools.execute_tool("read_file", filepath=filename)
                self.memory.log_task(f"Read file {filename}", "completed")
                return res_warn + result
        
        # List files / directory
        elif "list" in input_lower or "show files" in input_lower or input_lower == "ls" or input_lower.startswith("ls "):
            directory = "."
            words = user_input.split()
            if "in" in words:
                try:
                    idx = words.index("in")
                    if idx + 1 < len(words):
                        directory = words[idx + 1].rstrip('?.!')
                except ValueError:
                    pass
            elif len(words) > 1 and words[0] == "ls":
                directory = words[1].rstrip('?.!')
            result = await self.tools.execute_tool("list_files", directory=directory)
            self.memory.log_task(f"List files in {directory}", "completed")
            return result
        
        # Search files
        elif ("search" in input_lower or "find" in input_lower) and ("file" in input_lower or "files" in input_lower or "matching" in input_lower) and not ("google" in input_lower or "web" in input_lower):
            pattern = re.sub(r'^(search|find)\s+(for\s+)?(files?\s*)?(matching\s+)?', '', user_input, flags=re.I).strip().rstrip('?.!')
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
        
        # Add or check reminder
        elif "remind" in input_lower or "reminder" in input_lower:
            if any(kw in input_lower for kw in ["show", "list", "check", "where", "what", "pending"]):
                return self.get_pending_reminders_summary()
            
            reminder_text, due_at = self.parse_reminder_time(user_input)
            reminder = self.memory.add_reminder(reminder_text, due_date=due_at.isoformat())
            due_time_str = due_at.strftime("%H:%M:%S")
            return f"Reminder added for '{reminder_text}' (due at {due_time_str})."
        
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
        
        if not response_text or not response_text.strip():
            response_text = "Done, sir."

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
                    ui.render_user_message(f"🎤 (voice) {user_input}")
                except asyncio.TimeoutError:
                    # No voice input, get text input in a separate thread so event loop stays responsive
                    ui.set_state(UIState.IDLE)
                    user_input = await asyncio.to_thread(
                        ui.get_user_input
                    )
                    if user_input:
                        ui.render_user_message(user_input)
                
                if not user_input:
                    continue
                
                # Stop previous speech and cancel active speech task immediately on new message
                self.stop_speech()
                
                # Set busy state
                self.is_busy = True
                self.proactive_monitor.set_busy(True)
                
                # Render section divider
                ui.render_divider()

                # Process input with thinking status
                ui.start_thinking()
                try:
                    response = await self.process_command(user_input)
                finally:
                    ui.stop_thinking()
                
                if response is not None:
                    if not response or not response.strip():
                        response = "Done, sir."
                    # Display response using UI panel
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
                    response = "Done, sir."
                    ui.render_response(response)
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
