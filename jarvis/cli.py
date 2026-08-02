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
        
        # Session state
        self.running = True
        self.command_history = []
        self.voice_input_queue = asyncio.Queue()
        self.is_busy = False  # Track if JARVIS is busy (speaking, recording, etc.)
    
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
    
    async def process_command(self, user_input: str) -> Optional[str]:
        """Process user input and return response"""
        user_input = user_input.strip()
        
        # Handle slash commands
        if user_input.startswith("/"):
            return self._handle_slash_command(user_input)
        
        # Add to command history
        self.command_history.append(user_input)
        
        # Check for coding tasks and delegate to Claude Code
        if self._is_coding_task(user_input):
            return await self._delegate_to_claude_code(user_input)
        
        # Check for natural language tool commands
        tool_response = await self._check_tool_commands(user_input)
        if tool_response:
            return tool_response
        
        # Otherwise, send to AI
        return await self._get_ai_response(user_input)
    
    def _handle_slash_command(self, command: str) -> str:
        """Handle slash commands"""
        cmd_raw = command.strip()
        cmd_lower = cmd_raw.lower()
        
        if cmd_lower == "/help":
            self.show_help()
            return None
        elif cmd_lower == "/clear":
            console.clear()
            self.show_banner()
            return None
        elif cmd_lower == "/exit":
            self.running = False
            return "Goodbye! Have a great day!"
        elif cmd_lower == "/history":
            self.show_history()
            return None
        elif cmd_lower == "/tools":
            self.show_tools()
            return None
        elif cmd_lower == "/reminders":
            self.show_reminders()
            return None
        elif cmd_lower == "/notes":
            self.show_notes()
            return None
        elif cmd_lower == "/tasks":
            self.show_tasks()
            return None
        elif cmd_lower == "/profile":
            self.show_profile()
            return None
        elif cmd_lower == "/apps":
            self.show_apps()
            return None
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
            return None
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
        else:
            return f"Unknown command: {command}. Type /help for available commands."
    
    async def _check_tool_commands(self, user_input: str) -> Optional[str]:
        """Check if input matches a tool command"""
        input_lower = user_input.lower()
        
        # Open Application or Website
        if any(input_lower.startswith(prefix) for prefix in ["open ", "launch ", "start ", "run "]):
            words = user_input.split(maxsplit=1)
            if len(words) > 1:
                target = words[1].strip()
                target_lower = target.lower()
                
                # Exclude folder/directory commands
                if not ("folder" in target_lower or "directory" in target_lower or "file" in target_lower):
                    # Check website aliases first if website mentioned
                    if target_lower in WebsiteOpenTool.SITE_ALIASES or any(site in target_lower for site in ["youtube", "github", "gmail", "google", "reddit", "twitter"]):
                        result = await self.tools.execute_tool("open_website", site_name=target)
                        self.memory.log_task(f"Open website {target}", "completed")
                        return result
                    
                    # Try app launch
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
        if "create" in input_lower and ("folder" in input_lower or "directory" in input_lower):
            words = user_input.split()
            folder_name = words[-1] if words else "new_folder"
            result = await self.tools.execute_tool("directory", action="create", path=folder_name)
            self.memory.log_task(f"Create folder {folder_name}", "completed")
            return result
        
        # Read file
        elif "read" in input_lower and "file" in input_lower:
            words = user_input.split()
            filename = words[-1] if words else ""
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
            words = user_input.split()
            pattern = words[-1] if words else "*"
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
            if "to" in input_lower:
                reminder_text = input_lower.split("to")[-1].strip()
                reminder = self.memory.add_reminder(reminder_text)
                return f"Reminder added: {reminder_text}"
        
        # Add note
        elif input_lower.startswith("note:"):
            note_text = user_input[5:].strip()
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
        
        # Start proactive monitor
        self.proactive_monitor.start()
        
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
                
                # Set busy state
                self.is_busy = True
                self.proactive_monitor.set_busy(True)
                
                # Process input
                response = await self.process_command(user_input)
                
                if response:
                    # Display response using HUD UI panel
                    ui.render_response(response)
                    
                    # Speak response out loud every time
                    if self.voice_manager.enabled:
                        await self.voice_manager.speak_response(response)
                    else:
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
