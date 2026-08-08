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

from jarvis.api_client import JarvisAPIClient
from jarvis.tools import ToolRegistry

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
        
        # Initialize core systems
        console.print("[dim cyan]Initializing...[/]")
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
        else:
            return f"Unknown command: {cmd}. Try /help"
    
    async def _diagnose(self) -> str:
        lines = ["System Diagnostics:"]
        
        # DB check
        try:
            import sqlite3
            conn = sqlite3.connect('jarvis/data/jarvis.db')
            conn.execute("SELECT 1")
            conn.close()
            lines.append("✓ Database: connected")
        except Exception as e:
            lines.append(f"✗ Database: {e}")
        
        # API check
        try:
            import httpx
            r = httpx.get(
                "https://integrate.api.nvidia.com",
                timeout=5
            )
            lines.append("✓ NIM API: reachable")
        except:
            lines.append("✗ NIM API: unreachable")
        
        # Tools check
        lines.append(
            f"✓ Tools: {len(self.tools.tools)} registered"
        )
        
        # gh CLI check
        try:
            result = subprocess.run(
                ['gh', 'auth', 'status'],
                capture_output=True, timeout=5
            )
            if result.returncode == 0:
                lines.append("✓ GitHub CLI: authenticated")
            else:
                lines.append("✗ GitHub CLI: not authenticated")
        except:
            lines.append("✗ GitHub CLI: not found")
        
        return "\n".join(lines)
    
    def _show_help(self) -> str:
        return """JARVIS Commands:
/help         - This message
/exit         - Quit
/clear        - Clear screen  
/tools        - List all tools
/history      - Recent conversation
/context      - Check context usage
/context clear - Clear context history
/diagnose     - System health check
/speak on|off - Toggle voice output

Natural language — just talk:
"open notepad"
"create file notes.txt with content: hello"
"open youtube"
"show my github repos"
"copy hello world to clipboard"
"what's my cpu usage"
"search for python tutorials" """
    
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

def main():
    assistant = JarvisAssistant()
    asyncio.run(assistant.run())

if __name__ == "__main__":
    main()
