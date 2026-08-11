import asyncio
import os
import sys
import time
import subprocess
from dotenv import load_dotenv
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

# Find .env relative to this file's location
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

from jarvis.api_client import JarvisAPIClient, JarvisAPIClient as NIMClient
from jarvis.tools import ToolRegistry
from jarvis.diagnostics import run_diagnostics_sync
from jarvis.voice import ProactiveMonitor, VoiceManager
from jarvis.memory import Memory

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

console = Console()

BOOT_ART = """
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████╗
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
"""

class JarvisAssistant:
    def __init__(self):
        boot_start = time.time()
        self.voice_enabled = True
        
        # Show banner
        console.print(BOOT_ART, style="cyan")
        console.print(
            "Just A Rather Very Intelligent System",
            style="dim cyan", justify="center"
        )
        console.print(
            "Created by Nived  |  "
            "nvidia/nemotron-3-ultra-550b-a55b",
            style="dim white", justify="center"
        )
        console.rule(style="dim cyan")
        
        # Run startup health check
        console.print("[dim cyan]Running startup health check...[/]")
        from jarvis.health import HealthChecker
        checker = HealthChecker()
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                results = loop.run_until_complete(checker.run_all())
            else:
                results = asyncio.run(checker.run_all())
        except Exception:
            results = asyncio.run(checker.run_all())
        console.print(checker.render_results())
        if checker.critical_failures:
            console.print(f"[bold red][WARNING] Critical failures: {checker.critical_failures}[/bold red]")
            console.print("[yellow]JARVIS may not function correctly.[/yellow]")
        
        # Initialize core systems
        console.print("[dim cyan]Initializing core engine...[/]")
        self.api = JarvisAPIClient()
        self.tools = ToolRegistry()
        
        boot_time = time.time() - boot_start
        console.print(
            f"[green]✓ Online in {boot_time:.2f}s — "
            f"{len(self.tools.tools)} tools ready[/]"
        )
        
        # Boot voice greeting
        self._speak_boot_greeting()
    
    def _speak_boot_greeting(self):
        if not getattr(self, 'voice_enabled', True):
            return
        try:
            from jarvis.voice import speak
            from datetime import datetime
            h = datetime.now().hour
            greeting = (
                "Good morning" if h < 12 else
                "Good afternoon" if h < 18 else
                "Good evening"
            )
            # Schedule on the main event loop instead of creating a new one
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(speak(f"{greeting}, sir. All systems operational."))
            except RuntimeError:
                # No running loop, create one for this thread
                def run_greeting():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(speak(f"{greeting}, sir. All systems operational."))
                        loop.close()
                    except Exception as e:
                        print(f"[VOICE] Boot greeting error: {e}")
                import threading
                t = threading.Thread(target=run_greeting, daemon=True)
                t.start()
        except Exception as e:
            print(f"[VOICE] Boot greeting failed: {e}")
    
    async def _speak(self, text: str):
        if not getattr(self, 'voice_enabled', True):
            return
        # Skip very long responses — speak summary instead
        speak_text = text
        if len(text) > 400:
            speak_text = text[:400] + "..."
        # Skip debug lines
        if text.startswith('[') and ']' in text[:20]:
            return
        try:
            from jarvis.voice import speak
            # Schedule on the main event loop instead of creating a new thread with new loop
            loop = asyncio.get_running_loop()
            loop.create_task(speak(speak_text))
        except RuntimeError:
            # No running loop (shouldn't happen in async context), fallback to thread
            import threading
            def run_speak():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(speak(speak_text))
                    loop.close()
                except Exception as e:
                    print(f"[VOICE] Speak error: {e}")
            t = threading.Thread(target=run_speak, daemon=True)
            t.start()
        except ImportError:
            print("[VOICE] voice.py not found")
        except Exception as e:
            print(f"[VOICE] Error: {e}")
    
    async def _execute_tool(
        self, name: str, args: dict) -> str:
        return await self.tools.execute(name, args)
    
    async def _handle_slash_command(
        self, cmd: str) -> str:
        cmd = cmd.strip().lower()
        
        if cmd == '/help':
            return self._show_help()
        elif cmd == '/exit':
            console.print(
                "[cyan]JARVIS offline. Goodbye, sir.[/]")
            sys.exit(0)
        elif cmd == '/clear':
            console.clear()
            return "Screen cleared."
        elif cmd == '/tools':
            tools_list = list(self.tools.tools.keys())
            return f"Tools: {', '.join(tools_list)}"
        elif cmd == '/history':
            msgs = self.api.messages[-10:]
            lines = [
                f"{m['role'].upper()}: "
                f"{str(m.get('content',''))[:100]}"
                for m in msgs
            ]
            return "\n".join(lines) if lines \
                   else "No history."
        elif cmd == '/diagnose':
            return await self._diagnose()
        elif cmd == '/context':
            count = len(self.api.get_session("cli").messages)
            tokens = self.api.get_token_estimate("cli")
            return (f"Context: {count} messages, "
                    f"~{tokens} tokens estimated")
        elif cmd == '/context clear':
            self.api.clear_history("cli")
            return "Context cleared, sir."
        elif cmd == '/speak off':
            self.voice_enabled = False
            return "Voice disabled, sir."
        elif cmd == '/speak on':
            self.voice_enabled = True
            return "Voice enabled, sir."
        elif cmd.startswith('/calendar'):
            if not getattr(self.tools, 'calendar_service', None):
                return "Google Calendar service is unavailable."
            parts = cmd.split(maxsplit=2)
            subcmd = parts[1].lower() if len(parts) > 1 else "today"
            if subcmd in ("auth", "login"):
                auth_mgr = getattr(self.tools.calendar_service, 'auth_manager', None)
                if not auth_mgr:
                    return "GoogleAuthManager unavailable."
                ok, msg = auth_mgr.authenticate_interactive()
                return msg
            elif subcmd == "search":
                query = parts[2] if len(parts) > 2 else ""
                return self.tools.calendar_service.format_calendar_command(mode="search", query=query)
            elif subcmd in ("today", "tomorrow", "next"):
                return self.tools.calendar_service.format_calendar_command(mode=subcmd)
            else:
                return self.tools.calendar_service.format_calendar_command(mode="today")
        elif cmd.startswith('/email'):
            if not getattr(self.tools, 'email_service', None):
                return "Google Email service is unavailable."
            parts = cmd.split()
            subcmd = parts[1].lower() if len(parts) > 1 else ""
            if subcmd == "summary":
                return self.tools.email_service.generate_email_summary_briefing()
            elif subcmd in ("sent", "sent_list"):
                return self.tools.email_service.format_sent_list()
            elif subcmd == "delete":
                target = parts[2] if len(parts) > 2 else "1"
                if target.isdigit():
                    return self.tools.email_service.delete_sent_email_by_index(int(target))
                return self.tools.email_service.delete_sent_email_by_index(1)
            else:
                return self.tools.email_service.format_unread_list()
        elif cmd.startswith('/watch'):
            parts = cmd.split(maxsplit=3)
            symbol = parts[1].upper() if len(parts) > 1 else "AAPL"
            cond = parts[2] if len(parts) > 2 else "below"
            val = parts[3] if len(parts) > 3 else "1000"
            return f"Watching {symbol} {cond} {val}, sir."
        elif cmd.startswith('/trade'):
            parts = cmd.split()
            subcmd = parts[1].lower() if len(parts) > 1 else "log"
            sym = parts[2].upper() if len(parts) > 2 else "AAPL"
            op = parts[3].upper() if len(parts) > 3 else "BUY"
            return f"Trade logged: {subcmd} {sym} {op}, sir."
        else:
            return f"Unknown command: {cmd}. Try /help"
    
    async def _diagnose(self) -> str:
        report = run_diagnostics_sync()
        return report.format_plain()
    
    def _show_help(self) -> str:
        return """=====================================================
            J.A.R.V.I.S. SYSTEM COMMAND REFERENCE
=====================================================

--- SLASH COMMANDS ---
  /help            Show this command reference
  /tools           List all registered tool schemas
  /calendar        List today's Google Calendar schedule
  /email           Check recent unread emails in Gmail
  /email summary   Get executive email briefing
  /email sent      List recent sent emails
  /email delete 1  Delete sent email #1
  /diagnose        Run system diagnostics & health check
  /context       View active session token usage
  /context clear Reset session context memory
  /history       View recent conversation log
  /speak on|off  Toggle voice output
  /exit          Disconnect active session

--- GOOGLE CALENDAR COMMANDS ---
  • "what's on my calendar today?" / "/calendar"
  • "calendar tomorrow" / "/calendar tomorrow"
  • "what is my next event?" / "/calendar next"
  • "/calendar search <query>"
  • "schedule meeting titled Sync tomorrow at 15:00"

--- GMAIL & EMAIL COMMANDS ---
  • "check my email" / "/email"
  • "email summary" / "/email summary"
  • "read email 1" (reads body of email #1)
  • "send email to name@domain.com subject Title body Message"
  • "confirm" / "yes" (confirms draft send)

--- SYSTEM & UTILITIES ---
  • "what is my cpu usage?"
  • "get disk usage"
  • "open spotify" / "close notepad"
  • "copy hello world to clipboard"

--- DEVELOPER & GITHUB ---
  • "git status" / "git log"
  • "show my github repos"
  • "list open pull requests"

====================================================="""
    
    async def process_command(self, user_input: str) -> str:
        """Alias for backward compatibility with manual test runners."""
        return await self.process(user_input)

    async def process_single_command(self, user_input: str) -> str:
        """Alias for backward compatibility with manual test runners."""
        return await self.process(user_input)

    def _load_config(self):
        from jarvis.tools import _load_config
        return _load_config()

    async def process(self, user_input: str) -> str:
        user_input = user_input.strip()
        if not user_input:
            return None
        
        # Slash commands
        if user_input.startswith('/'):
            return await self._handle_slash_command(
                user_input)
        
        # Everything goes through LLM tool pipeline
        self.api.add_user_message(user_input, session_id="cli")
        return await self.api.chat_with_tools(
            tool_schemas=self.tools.schemas,
            tool_executor=self._execute_tool,
            session_id="cli"
        )
    
    async def run(self):
        console.print(
            "\n[dim cyan]Type anything or /help for commands."
            " /exit to quit.[/]\n"
        )
        
        while True:
            try:
                user_input = console.input(
                    "[cyan]◈ YOU  →  [/]"
                ).strip()
                
                if not user_input:
                    continue
                
                response = await self.process(user_input)
                
                if response:
                    console.print(Panel(
                        response,
                        title="[cyan]◈ JARVIS[/]",
                        border_style="cyan"
                    ))
                    
                    await self._speak(response)
                        
            except KeyboardInterrupt:
                console.print(
                    "\n[cyan]Goodbye, sir.[/]")
                break
            except EOFError:
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/]")

# Alias for backward compatibility with tests
JARVISCLI = JarvisAssistant

def main():
    assistant = JarvisAssistant()
    asyncio.run(assistant.run())

if __name__ == "__main__":
    main()
