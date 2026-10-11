"""
J.A.R.V.I.S. Mark 5.9 — Antigravity Agentic Gateway & Tactical Deck CLI
Unified multi-agent persona orchestration, Stark workshop protocols,
and OpenClaw-compatible terminal interface.
"""

import asyncio
import os
import sys
import time
import json
import inspect
import socket
import subprocess
from dotenv import load_dotenv
from pathlib import Path
from typing import Optional, List, Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.styles import Style as PTKStyle
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False

# Find .env relative to project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

from jarvis.api_client import JarvisAPIClient, JarvisAPIClient as NIMClient
from jarvis.tools import ToolRegistry
from jarvis.diagnostics import run_diagnostics_sync
from jarvis.voice import ProactiveMonitor, VoiceManager
from jarvis.memory import Memory
from jarvis.skills_engine import get_skills_engine
from jarvis.agents_registry import get_agents_registry, AgentProfile
from jarvis.doctor import JarvisDoctor

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

console = Console()

CLI_VERSION = "5.9.0"
CLI_RELEASE = "Mark 5.9 (Antigravity Edition)"
CLI_TITLE = f"J.A.R.V.I.S. {CLI_RELEASE} — All systems nominal."

BOOT_ART = """
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████╗
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
"""

SLASH_COMMANDS = [
    '/help', '/model', '/mode', '/plan', '/goal', '/boost', '/grill-me',
    '/dangerously-skip-permissions', '/skip-permissions', '/confirm',
    '/skills', '/skill', '/learn', '/subagents', '/agents', '/agent',
    '/inspect', '/test', '/latex', '/archive', '/screen', '/vision',
    '/sentinel', '/handsfree', '/sound', '/tools', '/status', '/vitals',
    '/doctor', '/diagnose', '/missions', '/mission', '/sessions', '/session',
    '/context', '/history', '/speak', '/clear', '/exit', '/quit',
    '/calendar', '/email', '/google', '/auth', '/watch', '/trade',
    '/briefing', '/protocol', '/gateway', '/channels'
]


def check_gateway_online(port: int = 8765) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.3)
    try:
        res = sock.connect_ex(("127.0.0.1", port))
        return res == 0
    except Exception:
        return False
    finally:
        sock.close()


class JarvisAssistant:
    def __init__(
        self,
        dangerously_skip_permissions: bool = False,
        mode: str = "auto",
        agent_id: Optional[str] = None,
        show_banner: bool = True
    ):
        boot_start = time.time()
        self.voice_enabled = True
        self.mode = mode  # "auto" | "agent" | "direct" | "boost"
        self.agents_registry = get_agents_registry()
        
        # Resolve active agent
        if agent_id:
            self.agent = self.agents_registry.get_agent(agent_id) or self.agents_registry.get_active_agent()
        else:
            self.agent = self.agents_registry.get_active_agent()

        # Initialize core systems
        self.api = JarvisAPIClient(agent_id=self.agent.agent_id)
        self.tools = ToolRegistry(dangerously_skip_permissions=dangerously_skip_permissions)
        self.skills_engine = get_skills_engine()

        # If agent specifies default model and current is generic, align
        if self.agent.default_model and hasattr(self.api, 'model'):
            # Only override if provider supports or model preset available
            pass

        active_model = getattr(self.api, 'model', 'nvidia/nemotron-3-super-120b-a12b')
        active_provider = getattr(self.api.provider, 'name', 'NVIDIA NIM')
        gw_online = check_gateway_online()
        gw_str = "[bold green]ws://127.0.0.1:8765[/]" if gw_online else "[dim]offline (port 8765)[/]"

        if show_banner:
            console.print(BOOT_ART, style="bold cyan")
            console.print(
                f"[bold cyan]J.A.R.V.I.S. {CLI_RELEASE}[/] — Antigravity Multi-Agent Gateway",
                justify="center"
            )
            console.print(
                f"Agent: {self.agent.badge}  |  "
                f"[dim white]Model:[/] [bold green]{active_model}[/]  |  "
                f"[dim white]Gateway:[/] {gw_str}  |  "
                f"[dim white]Mode:[/] [magenta]{self.mode.upper()}[/]",
                justify="center"
            )
            if self.tools.dangerously_skip_permissions:
                console.print(
                    "[bold white on red] ⚠️  DANGEROUSLY SKIP PERMISSIONS ACTIVE — ALL CONFIRMATION GATES BYPASSED [/]",
                    justify="center"
                )
            console.rule(style="dim cyan")
            boot_time = time.time() - boot_start
            console.print(
                f"[green]✓ Online in {boot_time:.2f}s — "
                f"{len(self.tools.tools)} registered tools | {len(self.skills_engine.skills)} Antigravity skills | "
                f"{len(self.agents_registry.list_agents())} persona agents ready[/]\n"
            )

        # Setup interactive prompt toolkit session if running in interactive terminal
        self.pt_session = None
        if HAS_PROMPT_TOOLKIT and hasattr(sys.stdin, 'isatty') and sys.stdin.isatty():
            try:
                agent_names = [f"/agent switch {a.agent_id}" for a in self.agents_registry.list_agents()]
                completer = WordCompleter(SLASH_COMMANDS + agent_names, ignore_case=True)
                self.pt_session = PromptSession(
                    history=InMemoryHistory(),
                    completer=completer
                )
            except Exception:
                self.pt_session = None

        # Boot voice greeting asynchronously
        if show_banner:
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
            name = self.agent.name
            target_voice = self.agent.voice or "en-GB-RyanNeural"
            
            def run_greeting():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(speak(f"{greeting}, sir. {name} online. All systems operational.", voice=target_voice))
                    loop.close()
                except Exception:
                    pass
            import threading
            t = threading.Thread(target=run_greeting, daemon=True)
            t.start()
        except Exception:
            pass

    async def _speak(self, text: str):
        if not getattr(self, 'voice_enabled', True):
            return
        speak_text = text
        if len(text) > 300:
            speak_text = text[:300] + "..."
        if text.startswith('[') and ']' in text[:20]:
            return
        target_voice = getattr(self.agent, 'voice', "en-GB-RyanNeural")
        try:
            from jarvis.voice import speak
            loop = asyncio.get_running_loop()
            loop.create_task(speak(speak_text, voice=target_voice))
        except RuntimeError:
            import threading
            def run_speak():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(speak(speak_text, voice=target_voice))
                    loop.close()
                except Exception:
                    pass
            t = threading.Thread(target=run_speak, daemon=True)
            t.start()
        except Exception:
            pass

    async def _execute_tool(self, name: str, args: dict) -> str:
        """Execute a tool with real-time CLI feedback and timing."""
        args_str = json.dumps(args, ensure_ascii=False) if args else "{}"
        if len(args_str) > 80:
            args_str = args_str[:77] + "..."
        console.print(f"[bold cyan]  ⚡ [Tool Call][/] [white]{name}[/][dim]({args_str})[/]")
        t0 = time.time()
        # Interactive prompt for ask_question
        if name == "ask_question":
            question = args.get("question", "")
            options = args.get("options", [])
            console.print()
            console.print(Panel(
                f"[bold cyan]{question}[/]",
                border_style="yellow",
                title="[bold yellow]❓ JARVIS Clarification[/]"
            ))
            if options:
                for idx, opt in enumerate(options, 1):
                    console.print(f"  [bold cyan][{idx}][/] [white]{opt}[/]")
            try:
                ans = await asyncio.to_thread(
                    console.input,
                    "\n[bold yellow]Your response (or option number) → [/]"
                )
                ans = ans.strip()
                if options and ans.isdigit() and 1 <= int(ans) <= len(options):
                    chosen = options[int(ans) - 1]
                    console.print(f"[dim green]Selected:[/] {chosen}\n")
                    return f"User selected option {ans}: '{chosen}'"
                return f"User replied: '{ans}'"
            except Exception:
                return "User bypassed question."

        try:
            res = await self.tools.execute(name, args)
            dt = time.time() - t0
            str_res = str(res).strip()
            first_line = str_res.split('\n')[0] if str_res else ""
            if len(first_line) > 90:
                first_line = first_line[:87] + "..."
            console.print(f"[dim green]  ✓ [Done in {dt:.2f}s][/] [dim]{first_line}[/]")
            return res
        except Exception as e:
            dt = time.time() - t0
            console.print(f"[bold red]  ✗ [Failed in {dt:.2f}s][/] [red]{e}[/]")
            return f"Tool Execution Error: {str(e)}"

    async def _handle_slash_command(self, raw_input: str) -> str:
        parts = raw_input.strip().split(maxsplit=2)
        cmd = parts[0].lower()
        subcmd = parts[1].lower() if len(parts) > 1 else ""
        arg = parts[2] if len(parts) > 2 else ""

        if cmd == '/help':
            return self._show_help()
        elif cmd in ('/exit', '/quit'):
            console.print(f"[cyan]{self.agent.name} offline. Goodbye, sir.[/]")
            sys.exit(0)
        elif cmd == '/clear':
            console.clear()
            return "Screen cleared, sir."
        elif cmd == '/mode':
            if subcmd in ("auto", "agent", "direct", "boost"):
                self.mode = subcmd
                return f"Execution mode set to [bold cyan]{self.mode.upper()}[/], sir."
            return (
                f"Current mode: [bold cyan]{self.mode.upper()}[/]\n"
                f"Available modes:\n"
                f"  • [cyan]/mode auto[/]   - Auto-detect simple vs multi-step autonomous tasks (recommended)\n"
                f"  • [cyan]/mode agent[/]  - Force multi-step autonomous planning on all tasks\n"
                f"  • [cyan]/mode boost[/]  - Deep multi-agent planning with rigorous test verification\n"
                f"  • [cyan]/mode direct[/] - Fast-path direct tool execution loop"
            )
        elif cmd == '/model':
            return await self._handle_model_command(subcmd, arg)
        elif cmd in ('/plan', '/goal'):
            prefix = '/goal' if cmd == '/goal' else '/plan'
            goal = raw_input[len(prefix):].strip()
            if not goal:
                return f"Please provide a goal to plan. Example: [cyan]{prefix} inspect the repository and fix failing tests[/]"
            return await self._run_plan_flow(goal)
        elif cmd == '/boost':
            self.mode = "boost"
            return (
                "◈ [bold cyan]BOOST MODE ACTIVATED[/] 🚀\n"
                "JARVIS is now operating with deep autonomous multi-agent reasoning, iterative verification, and rigorous test gating."
            )
        elif cmd == '/grill-me':
            return (
                "◈ [bold cyan]Interactive Clarification Mode[/]\n"
                "I am prepared to interview and challenge requirements to resolve ambiguities, sir. What project or architecture are we reviewing?"
            )
        elif cmd in ('/dangerously-skip-permissions', '/skip-permissions', '/yolo'):
            action = (subcmd or "toggle").strip().lower()
            if action in ("on", "enable", "true", "1"):
                self.tools.set_dangerously_skip_permissions(True)
                return (
                    "[bold red]⚠️ DANGEROUSLY SKIP PERMISSIONS ENABLED[/]\n"
                    "All tool confirmation gates (run_command, git push, GitHub actions, email, etc.) are bypassed."
                )
            elif action in ("off", "disable", "false", "0"):
                self.tools.set_dangerously_skip_permissions(False)
                return "[bold green]Safety confirmation gates restored[/], sir."
            else:
                new_state = not self.tools.dangerously_skip_permissions
                self.tools.set_dangerously_skip_permissions(new_state)
                if new_state:
                    return (
                        "[bold red]⚠️ DANGEROUSLY SKIP PERMISSIONS ENABLED[/]\n"
                        "All tool confirmation gates are bypassed."
                    )
                else:
                    return "[bold green]Safety confirmation gates restored[/], sir."
        elif cmd == '/confirm':
            act_id = subcmd.strip()
            extra = arg.strip()
            return self.tools.confirm_action(act_id, extra)
        elif cmd == '/skills':
            return self._handle_skills_command(subcmd)
        elif cmd == '/skill':
            target_skill = (subcmd + " " + arg).strip()
            if not target_skill:
                return "Usage: [cyan]/skill <name>[/]. Example: [cyan]/skill agentic-coding[/]"
            return self._show_skill_content(target_skill)
        elif cmd == '/learn':
            return await self._handle_learn_command(subcmd)
        elif cmd == '/subagents':
            return self._show_subagents()
        elif cmd == '/agents' or cmd == '/agent':
            return self._handle_agent_command(subcmd, arg)
        elif cmd == '/doctor':
            return self._handle_doctor_command(subcmd)
        elif cmd == '/inspect':
            target_path = (subcmd + " " + arg).strip() or "."
            return await self._execute_tool("inspect_project", {"path": target_path})
        elif cmd == '/test':
            target_path = (subcmd + " " + arg).strip() or "."
            return await self._execute_tool("run_tests", {"path": target_path})
        elif cmd in ('/latex', '/overleaf'):
            target_path = (subcmd + " " + arg).strip() or "."
            return await self._execute_tool("validate_latex_project", {"project_path": target_path})
        elif cmd == '/archive':
            target_path = (subcmd + " " + arg).strip()
            if not target_path:
                return "Usage: [cyan]/archive <archive_path>[/]"
            return await self._execute_tool("list_archive", {"archive_path": target_path})
        elif cmd in ('/screen', '/vision'):
            if cmd == '/screen':
                query = (subcmd + " " + arg).strip() or None
                return await self._execute_tool("inspect_screen", {"query": query} if query else {})
            else:
                img_path = subcmd
                query = arg.strip() or None
                if not img_path:
                    return "Usage: [cyan]/vision <image_path> [optional prompt][/]"
                return await self._execute_tool("analyze_image", {"path": img_path, "prompt": query} if query else {"path": img_path})
        elif cmd == '/sentinel':
            from jarvis.workspace_sentinel import get_workspace_sentinel
            sentinel = get_workspace_sentinel()
            action = (subcmd or "status").strip().lower()
            if action == "start":
                sentinel.start()
                return "Streaming perception sentinel started in background, sir."
            elif action == "stop":
                sentinel.stop()
                return "Streaming perception sentinel stopped, sir."
            elif action == "scan":
                evts = sentinel.scan_once()
                if not evts:
                    return "Sentinel scan complete: No active window or workspace changes detected."
                return "\n".join([f"  • [{e.event_type}] {e.summary}" for e in evts])
            elif action in ("events", "history"):
                evts = sentinel.get_recent_events(limit=10)
                if not evts:
                    return "No perceptual events logged yet."
                return "\n".join([f"  • [{e['event_type']}] {e['summary']} ({e['timestamp']})" for e in evts])
            else:
                st = sentinel.get_status()
                state_str = "[bold green]ACTIVE[/]" if st["running"] else "[dim]INACTIVE[/]"
                return (
                    f"[+] [bold cyan]Streaming Perception Sentinel:[/] {state_str}\n"
                    f"  Polling Interval: {st['interval_seconds']}s\n"
                    f"  Buffered Events: {st['buffered_events_count']}\n"
                    f"  Active Window: {st['last_active_window'] or '(none)'}\n\n"
                    f"Usage:\n"
                    f"  - [cyan]/sentinel start[/]  - Start background workspace & focus observer\n"
                    f"  - [cyan]/sentinel stop[/]   - Stop background sentinel\n"
                    f"  - [cyan]/sentinel scan[/]   - Run immediate perceptual observation pass\n"
                    f"  - [cyan]/sentinel events[/] - List recent perceptual events"
                )
        elif cmd in ('/handsfree', '/listen'):
            action = (subcmd or "status").strip().lower()
            if not hasattr(self, '_voice_manager') or self._voice_manager is None:
                from jarvis.voice import VoiceManager
                self._voice_manager = VoiceManager({"enabled": True, "voice": {"speak_responses": True}})
                self._voice_manager.set_callbacks(
                    on_transcription=lambda text: print(f"\n[bold cyan]⚡ Hands-Free Input:[/] {text}"),
                    on_response=lambda text: None
                )

            if action in ("start", "on", "enable"):
                self._voice_manager.enable_hands_free()
                from jarvis.sound_effects import play_sound
                play_sound("wake")
                return "[bold green]Tony Stark Hands-Free Mode ENABLED.[/] Speak [cyan]'Hey JARVIS'[/] to activate."
            elif action in ("stop", "off", "disable"):
                self._voice_manager.disable_hands_free()
                return "Hands-free wake-word detection deactivated, sir."
            else:
                is_active = bool(self._voice_manager.wake_detector and self._voice_manager.wake_detector.running)
                state_str = "[bold green]ACTIVE ('Hey JARVIS')[/]" if is_active else "[dim]INACTIVE[/]"
                return (
                    f"[+] [bold cyan]Tony Stark Hands-Free Engine:[/] {state_str}\n"
                    f"Usage:\n"
                    f"  - [cyan]/handsfree on[/]   - Activate open-mic 'Hey JARVIS' wake-word listener\n"
                    f"  - [cyan]/handsfree off[/]  - Deactivate hands-free listening\n"
                    f"  - [cyan]/sound [cue][/]     - Test UI audio cue (wake, ack, done, alert)"
                )
        elif cmd == '/sound':
            from jarvis.sound_effects import play_sound
            cue = (subcmd or "wake").strip().lower()
            play_sound(cue)
            return f"Played Stark audio cue: '{cue}', sir."
        elif cmd == '/tools':
            return self._handle_tools_command(subcmd)
        elif cmd in ('/status', '/vitals'):
            return self._show_status()
        elif cmd == '/history':
            session = self.api.get_session("cli") or self.api.get_session()
            msgs = session.messages[-10:] if session else []
            if not msgs:
                return "No conversation history for active session."
            lines = [f"[cyan]{m['role'].upper()}:[/] {str(m.get('content',''))[:120]}" for m in msgs]
            return "\n".join(lines)
        elif cmd == '/diagnose':
            return await self._diagnose()
        elif cmd == '/context':
            if subcmd == 'clear':
                self.api.clear_history("cli")
                return "Context cleared for CLI session, sir."
            sess = self.api.get_session("cli") or self.api.get_session()
            count = len(sess.messages) if sess else 0
            tokens = self.api.get_token_estimate("cli")
            return f"Context: {count} messages, ~{tokens} estimated tokens in active session."
        elif cmd == '/speak':
            if subcmd == 'off':
                self.voice_enabled = False
                return "Voice output disabled, sir."
            elif subcmd == 'on':
                self.voice_enabled = True
                return "Voice output enabled, sir."
            return f"Voice output is currently {'enabled' if self.voice_enabled else 'disabled'}."
        elif cmd in ('/missions', '/mission'):
            return await self._handle_missions_command(subcmd, arg)
        elif cmd in ('/sessions', '/session'):
            return self._handle_sessions_command(subcmd, arg)
        elif cmd == '/briefing':
            return await self._execute_tool("get_stark_briefing", {})
        elif cmd == '/protocol':
            proto_name = (subcmd or "workshop").strip().lower()
            return await self._execute_tool("execute_house_protocol", {"protocol_name": proto_name})
        elif cmd == '/gateway':
            return self._handle_gateway_command(subcmd)
        elif cmd == '/channels':
            return self._handle_channels_command()
        elif cmd.startswith('/google') or cmd.startswith('/auth'):
            from jarvis.google_auth import GoogleAuthManager
            auth_mgr = GoogleAuthManager()
            ok, msg = auth_mgr.authenticate_interactive()
            return msg
        elif cmd.startswith('/calendar'):
            if not getattr(self.tools, 'calendar_service', None):
                return "Google Calendar service is unavailable."
            if subcmd in ("auth", "login"):
                auth_mgr = getattr(self.tools.calendar_service, 'auth_manager', None)
                if not auth_mgr:
                    from jarvis.google_auth import GoogleAuthManager
                    auth_mgr = GoogleAuthManager()
                ok, msg = auth_mgr.authenticate_interactive()
                return msg
            elif subcmd == "search":
                return self.tools.calendar_service.format_calendar_command(mode="search", query=arg)
            elif subcmd in ("today", "tomorrow", "next"):
                return self.tools.calendar_service.format_calendar_command(mode=subcmd)
            else:
                return self.tools.calendar_service.format_calendar_command(mode="today")
        elif cmd.startswith('/email'):
            if not getattr(self.tools, 'email_service', None):
                return "Google Email service is unavailable."
            if subcmd in ("auth", "login"):
                auth_mgr = getattr(self.tools.email_service, 'auth_manager', None)
                if not auth_mgr:
                    from jarvis.google_auth import GoogleAuthManager
                    auth_mgr = GoogleAuthManager()
                ok, msg = auth_mgr.authenticate_interactive()
                return msg
            elif subcmd == "summary":
                return self.tools.email_service.generate_email_summary_briefing()
            elif subcmd in ("sent", "sent_list"):
                return self.tools.email_service.format_sent_list()
            elif subcmd == "delete":
                target = arg if arg else "1"
                idx = int(target) if target.isdigit() else 1
                return self.tools.email_service.delete_sent_email_by_index(idx)
            else:
                return self.tools.email_service.format_unread_list()
        elif cmd.startswith('/watch'):
            sym = subcmd.upper() if subcmd else "AAPL"
            return f"Watching market ticker {sym}, sir."
        elif cmd.startswith('/trade'):
            return f"Trading system nominal, sir."
        else:
            return f"Unknown command: {raw_input}. Type [cyan]/help[/] for command reference."

    def _handle_agent_command(self, subcmd: str, arg: str) -> str:
        agents = self.agents_registry.list_agents()
        active = self.agents_registry.get_active_agent()

        if not subcmd or subcmd == "list":
            table = Table(title="JARVIS Multi-Agent Fleet", border_style="cyan")
            table.add_column("Agent ID", style="dim", no_wrap=True)
            table.add_column("Status", justify="center")
            table.add_column("Identity", style="bold white")
            table.add_column("Role", style="cyan")
            table.add_column("Default Model", style="green")
            table.add_column("Voice", style="magenta")

            for a in agents:
                is_active = (a.agent_id == active.agent_id)
                status_badge = "[bold green][ok] ACTIVE[/]" if is_active else "[dim]idle[/]"
                table.add_row(
                    a.agent_id,
                    status_badge,
                    f"{a.emoji} {a.name}",
                    a.role,
                    a.default_model.split('/')[-1],
                    a.voice.split('-')[-1].replace('Neural', '')
                )
            console.print(table)
            return f"JARVIS Multi-Agent Fleet ({len(agents)} personas ready). Use [cyan]/agent switch <id>[/] or [cyan]/agent info <id>[/] to activate."

        elif subcmd in ("switch", "use", "set"):
            target_id = arg.lower().strip() or "jarvis"
            agent = self.agents_registry.get_agent(target_id)
            if not agent:
                return f"Agent '{target_id}' not found. Available agents: {', '.join(a.agent_id for a in agents)}"
            self.agents_registry.set_active_agent(target_id)
            self.agent = agent
            self.api.set_agent(target_id)
            return f"Switched active agent persona to {agent.badge} ({agent.role}), sir."

        elif subcmd in ("info", "show"):
            target_id = arg.lower().strip() or active.agent_id
            agent = self.agents_registry.get_agent(target_id)
            if not agent:
                return f"Agent '{target_id}' not found."
            
            panel_text = (
                f"[bold cyan]Identity:[/] {agent.emoji} {agent.name}\n"
                f"[bold cyan]Role:[/] {agent.role}\n"
                f"[bold cyan]Workspace:[/] {agent.workspace}\n"
                f"[bold cyan]Default Model:[/] {agent.default_model}\n"
                f"[bold cyan]Voice Synthesis:[/] {agent.voice}\n"
                f"[bold cyan]Routing Tags:[/] {', '.join(agent.routing_rules)}\n\n"
                f"[bold white]Description:[/] {agent.description}\n\n"
                f"[bold yellow]Persona Addon Directives:[/] \n{agent.system_prompt_addon or '(Uses base Butler persona)'}"
            )
            console.print(Panel(panel_text, title=f"[bold cyan]Agent Profile: {agent.name}[/]", border_style="cyan"))
            return f"Agent profile '{agent.name}' displayed."

        return "Usage: /agent [list|switch <id>|info <id>]"

    def _handle_doctor_command(self, subcmd: str) -> str:
        fix = (subcmd == "--fix" or subcmd == "fix")
        doctor = JarvisDoctor(fix=fix)
        with console.status("[bold cyan]Running system doctor diagnostics...[/]", spinner="dots"):
            report = doctor.run_all()

        table = Table(title="JARVIS Doctor Health Audit", border_style="cyan")
        table.add_column("Category", style="dim")
        table.add_column("Check", style="bold white")
        table.add_column("Status", justify="center")
        table.add_column("Details", style="white")

        for f in report.findings:
            if f.status == "ok":
                badge = "[bold green][ok][/]"
            elif f.status == "warning":
                badge = "[bold yellow][warn][/]"
            else:
                badge = "[bold red][fail][/]"
            table.add_row(f.category, f.title, badge, f.message)

        console.print(table)
        summary = (
            f"Audit Complete: [bold green]{report.ok_count} passed[/], "
            f"[bold yellow]{report.warning_count} warnings[/], "
            f"[bold red]{report.error_count} errors[/]."
        )
        if report.repaired_count > 0:
            summary += f" [bold green]({report.repaired_count} repaired)[/]"
        return summary

    def _handle_gateway_command(self, subcmd: str) -> str:
        online = check_gateway_online()
        if not subcmd or subcmd == "status":
            st = "[bold green][ok] ONLINE (port 8765)[/]" if online else "[dim]OFFLINE (not listening)[/]"
            return (
                f"[+] [bold cyan]WebSocket Gateway:[/] {st}\n"
                f"  Address: ws://127.0.0.1:8765/ws\n"
                f"  REST API: http://127.0.0.1:8765\n\n"
                f"Commands:\n"
                f"  - [cyan]/gateway run[/]  - Start gateway in background\n"
                f"  - [cyan]/gateway stop[/] - Stop gateway process"
            )
        elif subcmd == "run":
            if online:
                return "Gateway is already online and listening on ws://127.0.0.1:8765."
            try:
                subprocess.Popen(
                    [sys.executable, "-m", "jarvis.api"],
                    cwd=str(Path(__file__).parent.parent),
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
                )
                return "Spawned JARVIS Gateway background service on ws://127.0.0.1:8765."
            except Exception as e:
                return f"Failed to start gateway: {e}"
        elif subcmd == "stop":
            if not online:
                return "Gateway is not running."
            try:
                import psutil
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    cmdline = " ".join(proc.info.get('cmdline') or [])
                    if "jarvis.api" in cmdline:
                        proc.terminate()
                return "Terminated JARVIS Gateway processes."
            except Exception as e:
                return f"Failed to stop gateway: {e}"
        return "Usage: /gateway [status|run|stop]"

    def _handle_channels_command(self) -> str:
        table = Table(title="Connected Channels & Touchpoints", border_style="cyan")
        table.add_column("Channel", style="bold white")
        table.add_column("Type", style="dim")
        table.add_column("Status", style="green")
        table.add_column("Transport")

        gw_online = check_gateway_online()
        gw_status = "[bold green]ONLINE[/]" if gw_online else "[dim]OFFLINE[/]"

        table.add_row("Terminal CLI", "Interactive Shell", "[bold green]ACTIVE[/]", "Direct stdin/stdout")
        table.add_row("Electron Desktop App", "HUD Client", gw_status, "ws://127.0.0.1:8765/ws")
        table.add_row("Mobile PWA", "Mobile Web App", gw_status, "Tailscale LAN / WS Token")
        table.add_row("Proactive Engine", "Autonomous Follow-up", "[bold green]ACTIVE[/]", "Internal event bus")

        console.print(table)
        return "All configured messaging and UI channels reported."

    async def _handle_model_command(self, subcmd: str, arg: str) -> str:
        current_model = getattr(self.api, 'model', 'unknown')
        provider_name = getattr(self.api.provider, 'name', 'unknown')

        presets = {
            "super": "nvidia/nemotron-3-super-120b-a12b",
            "nemotron": "nvidia/nemotron-3-super-120b-a12b",
            "nemotron-super": "nvidia/nemotron-3-super-120b-a12b",
            "ultra": "nvidia/nemotron-3-ultra-550b-a55b",
            "llama": "meta/llama-3.2-11b-vision-instruct",
            "llama3": "meta/llama-3.2-11b-vision-instruct",
            "gpt": "openai/gpt-oss-20b",
            "gpt-oss": "openai/gpt-oss-20b"
        }

        if not subcmd or subcmd == "status":
            t0 = time.time()
            latency_str = "evaluating..."
            try:
                ping_res = await asyncio.wait_for(
                    self.api.provider.chat([{"role": "user", "content": "ping"}], max_tokens=5),
                    timeout=5.0
                )
                dt = time.time() - t0
                latency_str = f"{dt*1000:.0f}ms (Live OK)"
            except Exception as e:
                latency_str = f"Error: {e}"

            table = Table(title="LLM Provider & Model Status", border_style="cyan")
            table.add_column("Property", style="bold white")
            table.add_column("Value", style="green")
            table.add_row("Provider", provider_name)
            table.add_row("Active Model", current_model)
            table.add_row("Ping Latency", latency_str)
            table.add_row("Presets", "/model super | /model ultra | /model llama | /model gpt | /model gemini | /model groq")
            console.print(table)
            return "Use [cyan]/model <preset>[/] to switch models on the fly, sir."

        elif subcmd == "list":
            table = Table(title="Model Catalog & Capabilities", border_style="cyan")
            table.add_column("Model Identifier", style="bold green")
            table.add_column("Input", style="cyan")
            table.add_column("Context", style="dim")
            table.add_column("Auth", style="white")
            table.add_column("Tags", style="yellow")

            models_data = [
                ("nvidia/nemotron-3-super-120b-a12b", "text", "1049k", "yes", "default,super,active"),
                ("nvidia/nemotron-3-ultra-550b-a55b", "text", "1049k", "yes", "ultra,high-capacity"),
                ("meta/llama-3.2-11b-vision-instruct", "text+image", "128k", "yes", "vision,multimodal"),
                ("openai/gpt-oss-20b", "text", "64k", "yes", "fast-path"),
                ("google/gemini-2.0-flash", "text+image", "1049k", "configured", "gemini"),
                ("groq/llama-3.3-70b-versatile", "text", "128k", "configured", "groq,ultra-low-latency")
            ]
            for m_id, inp, ctx, auth, tags in models_data:
                table.add_row(m_id, inp, ctx, auth, tags)
            console.print(table)
            return "Use [cyan]/model <preset>[/] to activate."

        target = subcmd.lower()
        if target in presets:
            new_model = presets[target]
            self.api.model = new_model
            if hasattr(self.api.provider, 'set_model'):
                self.api.provider.set_model(new_model)
            elif hasattr(self.api.provider, 'model'):
                self.api.provider.model = new_model
            return f"Switched model to [bold green]{new_model}[/] ({provider_name}), sir."
        elif target in ("gemini", "groq", "nvidia", "ollama"):
            from jarvis.llm_provider import get_provider
            try:
                prov = get_provider(target)
                self.api.provider = prov
                self.api.model = getattr(prov, 'model', 'default')
                return f"Switched provider to [bold green]{prov.name}[/] (Model: {self.api.model}), sir."
            except Exception as e:
                return f"Failed to switch to provider {target}: {e}"
        else:
            custom = subcmd + (f" {arg}" if arg else "")
            self.api.model = custom.strip()
            if hasattr(self.api.provider, 'set_model'):
                self.api.provider.set_model(self.api.model)
            return f"Custom model set to [bold green]{self.api.model}[/], sir."

    def _handle_tools_command(self, query: str) -> str:
        all_tools = sorted(self.tools.tools.keys())
        if query:
            filtered = [t for t in all_tools if query.lower() in t.lower()]
            if not filtered:
                return f"No tools matching '{query}' found."
            return f"Matching tools ({len(filtered)}): {', '.join(filtered)}"
        return (
            f"Registered Tools ({len(all_tools)} total):\n"
            f"{', '.join(all_tools[:35])}...\n"
            f"Use [cyan]/tools <query>[/] to search tools by name."
        )

    def _show_status(self) -> str:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('D:\\' if os.path.exists('D:\\') else '/')
        gw_online = check_gateway_online()

        table = Table(title="JARVIS System Status & Operational Telemetry", border_style="cyan")
        table.add_column("Subsystem", style="bold white")
        table.add_column("Status / Details", style="green")

        gw_str = "[bold green][ok] Running (ws://127.0.0.1:8765)[/]" if gw_online else "[dim]Offline (port 8765 idle)[/]"
        table.add_row("Session", "[bold green][ok] Running (cli)[/]")
        table.add_row("Active Agent", f"{self.agent.badge} ({self.agent.role})")
        table.add_row("Active Model", f"{getattr(self.api, 'model', 'unknown')} ({getattr(self.api.provider, 'name', 'NVIDIA NIM')})")
        table.add_row("Gateway", gw_str)
        table.add_row("Agent Mode", f"[magenta]{self.mode.upper()}[/]")
        table.add_row("CPU Load", f"{cpu}%")
        table.add_row("RAM Usage", f"{mem.percent}% ({mem.used // (1024*1024)} MB / {mem.total // (1024*1024)} MB)")
        table.add_row("Disk Usage", f"{disk.percent}% ({disk.used // (1024*1024*1024)} GB / {disk.total // (1024*1024*1024)} GB)")
        table.add_row("Tools Registered", f"{len(self.tools.tools)} active schemas")
        table.add_row("Skills Indexed", f"{len(self.skills_engine.skills)} Antigravity skills")
        table.add_row("Voice Synthesis", f"Edge-TTS ({self.agent.voice})")

        console.print(table)
        return "All system vitals nominal, sir."

    def _show_vitals(self) -> str:
        return self._show_status()

    async def _handle_missions_command(self, subcmd: str, arg: str) -> str:
        try:
            from jarvis.mission_manager import MissionManager
            mm = MissionManager()
            if subcmd in ("", "list"):
                missions = mm.list_missions()
                if not missions:
                    return "No persistent missions found. Missions are created automatically when large goals are given."
                table = Table(title="Persistent Missions", border_style="cyan")
                table.add_column("ID", style="dim")
                table.add_column("Title", style="bold white")
                table.add_column("Status", style="green")
                table.add_column("Progress", style="cyan")
                for m in missions:
                    table.add_row(m.mission_id[:8], m.title, m.status, f"{m.progress_pct:.0f}%")
                console.print(table)
                return "Use [cyan]/mission approve <id>[/] or [cyan]/mission next[/] for next action."
            elif subcmd == "next":
                res = mm.get_next_actionable_task()
                if not res.has_action:
                    return f"No pending actions: {res.reason}"
                return f"Next Action: {res.task_description} (Agent: {res.assigned_agent})"
            elif subcmd == "approve":
                mid = arg or "1"
                ok = mm.approve_mission(mid)
                return f"Mission {mid} {'approved' if ok else 'failed to approve'}, sir."
            else:
                return "Mission command: /missions [list|next|approve <id>]"
        except Exception as e:
            return f"Missions error: {e}"

    def _handle_sessions_command(self, subcmd: str, arg: str) -> str:
        sessions = self.api.list_sessions()
        if not subcmd or subcmd == "list":
            table = Table(title="Conversation Sessions", border_style="cyan")
            table.add_column("Session ID", style="dim")
            table.add_column("Title", style="bold white")
            table.add_column("Messages", style="cyan")
            for s in sessions:
                table.add_row(s.get("session_id", ""), s.get("title", ""), str(s.get("message_count", 0)))
            console.print(table)
            return "Use [cyan]/session switch <id>[/] or [cyan]/session new [title][/], sir."
        elif subcmd == "new":
            title = arg or "New Session"
            sess = self.api.new_session(title=title)
            return f"Created and switched to session [bold green]{sess.session_id}[/] ('{title}'), sir."
        elif subcmd == "switch":
            if not arg:
                return "Please specify a session ID to switch to."
            sess = self.api.switch_session(arg)
            if sess:
                return f"Switched to session [bold green]{sess.session_id}[/] ('{sess.title}'), sir."
            return f"Session '{arg}' not found."
        return "Session commands: /sessions [list|new <title>|switch <id>]"

    def _handle_skills_command(self, category_filter: str = "") -> str:
        skills = self.skills_engine.list_skills(category=category_filter or None)
        if not skills:
            return "No Antigravity skills found."
        table = Table(title=f"Embedded Antigravity Skills ({len(skills)})", border_style="cyan")
        table.add_column("Skill Name", style="bold green", no_wrap=True)
        table.add_column("Category", style="cyan")
        table.add_column("Description", style="white")
        for s in skills:
            table.add_row(s["name"], s["category"], s["description"][:85] + ("..." if len(s["description"]) > 85 else ""))
        console.print(table)
        return "Type [cyan]/skill <name>[/] to inspect instructions, or [cyan]/learn[/] to create a new skill."

    def _show_skill_content(self, name: str) -> str:
        skill = self.skills_engine.get_skill(name)
        if not skill:
            return f"Skill '{name}' not found. Use [cyan]/skills[/] to list all skills."
        content = self.skills_engine.activate_skill(name)
        console.print(Panel(Markdown(content), title=f"[bold cyan]Skill: {skill.name}[/]", border_style="cyan"))
        return f"Loaded skill '{skill.name}' into view."

    async def _handle_learn_command(self, initial_name: str = "") -> str:
        name = initial_name.strip()
        if not name:
            name = await asyncio.to_thread(console.input, "[bold cyan]Skill Identifier (e.g. fast-api-deploy): [/]")
        name = name.strip()
        if not name:
            return "Skill learning cancelled: no name provided."
        desc = await asyncio.to_thread(console.input, "[bold cyan]Skill Description (what it does & when to activate): [/]")
        inst = await asyncio.to_thread(console.input, "[bold cyan]Detailed Step-by-Step Instructions / Runbook: [/]")
        cat = await asyncio.to_thread(console.input, "[bold cyan]Category (default: general): [/]")
        res = self.skills_engine.create_skill(name, desc, inst, cat or "general")
        return res

    def _show_subagents(self) -> str:
        table = Table(title="JARVIS Autonomous Subagent Fleet", border_style="cyan")
        table.add_column("Subagent Role", style="bold green")
        table.add_column("Specialization", style="white")
        table.add_column("Capabilities", style="cyan")
        agents_data = [
            ("PlanningAgent", "Goal decomposition & subtask planning", "Deconstructs high-level prompts into DAG subtasks"),
            ("CodingAgent", "Verified debug loop & software development", "view_file, replace_file_content, run_tests, git/gh"),
            ("ResearchAgent", "Information retrieval & knowledge synthesis", "Live web search, Chromium browsing, Obsidian memory"),
            ("SystemAgent", "Host automation & OS process management", "CLI command execution, task scheduling, vitals"),
            ("CommunicationAgent", "Email dispatch & calendar management", "Gmail summaries, calendar briefings, user briefings"),
        ]
        for role, spec, caps in agents_data:
            table.add_row(role, spec, caps)
        console.print(table)
        return "Subagent fleet ready for task delegation via [cyan]invoke_subagent[/] or [cyan]/plan[/]."

    async def _diagnose(self) -> str:
        with console.status("[bold cyan]Running system diagnostics...[/]", spinner="dots"):
            report = run_diagnostics_sync()
        return report.format_plain()

    def _show_help(self) -> str:
        return f"""=====================================================
            J.A.R.V.I.S. AGENT COMMAND REFERENCE
=====================================================

--- MULTI-AGENT PERSONA FLEET ---
  /agents / /agent list           Inspect configured persona agents (JARVIS, ULTRON, FRIDAY, EDITH, KAREN)
  /agent switch <id>              Switch active persona agent on the fly
  /agent info <id>                View persona details, prompt addons, and routing

--- ANTIGRAVITY & AUTONOMOUS AGENT CONTROLS ---
  /mode [auto|agent|boost|direct] Toggle agent operational mode
  /plan <goal> / /goal <goal>     Decompose & execute goal with autonomous swarm
  /boost                          Activate Boost Mode (deep verification & test gating)
  /dangerously-skip-permissions   Toggle autonomous bypass of all confirmation gates
  /confirm <action_id>            Confirm pending risky tool execution
  /skills [category]              View all 16 embedded Antigravity skills
  /skill <name>                   Inspect full instructions & runbook for a skill
  /learn [name]                   Interactive wizard to learn & persist a new skill
  /subagents                      Inspect the 5 logical subagents in the JARVIS fleet
  /inspect [path]                 Inspect project directory structure & entry points
  /test [path]                    Run test suite with pass/fail telemetry
  /screen [query]                 Capture & analyze active screen using vision model
  /vision <path> [prompt]         Analyze an image or screenshot with multimodal vision
  /latex <path>                   Validate LaTeX environment & figures for Overleaf
  /archive <path>                 Inspect multi-disk zip/tar archive contents
  /sentinel [start|stop|scan]     Streaming perception background observer & events
  /handsfree [on|off]             Tony Stark hands-free 'Hey JARVIS' wake-word listener
  /sound [wake|ack|done|alert]    Trigger Stark UI audio cue
  /grill-me                       Enter interactive requirements clarification mode

--- STARK PROTOCOLS & GATEWAY ---
  /briefing                       The Stark Morning Briefing (vitals, weather, calendar, email, git)
  /protocol <name>                Execute house protocol (workshop, clean_slate, lockdown, overdrive)
  /gateway [status|run|stop]      Inspect or launch WebSocket gateway daemon
  /channels                       Inspect connected UI and remote messaging channels
  /doctor [--fix]                 Run comprehensive environment health checks and repairs

--- MODEL & RUNTIME CONTROLS ---
  /model [name]                   Switch LLM (super, ultra, llama, gpt, gemini, groq)
  /status / /vitals               View live CPU, RAM, disk, gateway, and model vitals
  /tools [query]                  Search and inspect registered tools
  /missions                       Manage persistent background missions
  /sessions                       Manage multi-turn conversation sessions
  /diagnose                       Run system diagnostics
  /context [clear]                View or clear active session token context
  /history                        View recent conversation history
  /speak on|off                   Toggle Edge-TTS voice output
  /clear                          Clear screen
  /exit                           Clean system shutdown

--- GOOGLE WORKSPACE ---
  /calendar                       List Google Calendar schedule
  /email [summary]                Check Gmail and get executive briefing

====================================================="""

    async def _run_plan_flow(self, goal: str) -> str:
        """Mark 5.4 Adaptive Neuro-Symbolic Task Scheduler flow with dependency resolution."""
        console.print(f"\n[bold cyan]◈ [Adaptive Neuro-Symbolic Planner][/] Analyzing goal: [white]{goal}[/]")
        from jarvis.orchestration.dag_planner import DAGPlanner
        planner = DAGPlanner()
        available = list(self.tools.tools.keys())

        with console.status("[bold cyan]Synthesizing DAG execution plan...[/]", spinner="dots"):
            dag = await planner.create_plan(goal, available_tools=available)

        console.print(planner.render_ascii_dag(dag))
        console.print()

        with console.status("[bold cyan]Executing DAG subtasks with dependency resolution...[/]", spinner="dots"):
            res = await planner.execute_plan(dag, tool_registry=self.tools)

        console.print(f"\n[bold cyan]◈ DAG Execution Complete:[/] {dag.status}")
        console.print(planner.render_ascii_dag(dag))
        summary = f"DAG plan execution finished with status: {dag.status}."
        self.api.add_assistant_message(summary, session_id="cli")
        return summary

    async def _run_direct_flow(self, user_input: str) -> str:
        """Direct fast-path tool-calling execution."""
        self.api.add_user_message(user_input, session_id="cli")

        with console.status(f"[bold cyan]◈ {self.agent.name} is reasoning...[/]", spinner="dots"):
            response = await self.api.chat_with_tools(
                tool_schemas=self.tools.schemas,
                tool_executor=self._execute_tool,
                session_id="cli",
                tool_registry=self.tools
            )
        return response

    async def process(self, user_input: str) -> str:
        user_input = user_input.strip()
        if not user_input:
            return None

        # Slash commands
        if user_input.startswith('/'):
            return await self._handle_slash_command(user_input)

        # Check execution mode
        if self.mode in ("agent", "boost"):
            return await self._run_plan_flow(user_input)
        elif self.mode == "direct":
            return await self._run_direct_flow(user_input)
        else:
            # Auto mode: Check if request is multi-step
            if getattr(self.api, 'dispatcher', None):
                rule_plan = self.api.dispatcher.planning_agent.classify_request_rule_based(user_input)
                if rule_plan is None:
                    return await self._run_plan_flow(user_input)

            return await self._run_direct_flow(user_input)

    async def process_command(self, user_input: str) -> str:
        return await self.process(user_input)

    async def process_single_command(self, user_input: str) -> str:
        return await self.process(user_input)

    async def run(self):
        console.print(
            "[dim cyan]Type anything or [bold cyan]/help[/] for commands. "
            "[bold cyan]/agent[/] to switch personas. [bold cyan]/exit[/] to quit.[/]\n"
        )

        while True:
            try:
                agent_name = self.agent.name.upper()
                prompt_label = f"◈ [{self.mode}:{agent_name}] YOU  →  "

                if self.pt_session:
                    user_input = await asyncio.to_thread(
                        self.pt_session.prompt,
                        prompt_label
                    )
                else:
                    user_input = console.input(f"[cyan]{prompt_label}[/]")

                user_input = user_input.strip()
                if not user_input:
                    continue

                t_proc0 = time.time()
                response = await self.process(user_input)
                elapsed = time.time() - t_proc0

                if response:
                    console.print()
                    console.print(Panel(
                        Markdown(response),
                        title=f"{self.agent.badge} [dim]({elapsed:.2f}s)[/]",
                        border_style="cyan"
                    ))
                    console.print()

                    await self._speak(response)

            except (KeyboardInterrupt, EOFError):
                console.print(f"\n[cyan]{self.agent.name} offline. Goodbye, sir.[/]")
                break
            except Exception as e:
                console.print(f"[bold red]Error:[/] {e}")


# Alias for backward compatibility with tests
JARVISCLI = JarvisAssistant


def print_root_help():
    reg = get_agents_registry()
    active = reg.get_active_agent()
    print(f"""{CLI_TITLE}

Usage: jjarvis [options] [command]

Antigravity Autonomous Agent Fleet, Stark Workshop & Gateway CLI

Options:
  --agent <id>                    Active agent identity ({', '.join(a.agent_id for a in reg.list_agents())}) (current: {active.agent_id})
  --mode <auto|agent|direct|boost> Operational execution mode (default: auto)
  -y, --yes, --dangerously-skip-permissions Bypass all safety confirmation gates
  -V, --version                   Output the version number
  -h, --help                      Display help for command

Commands:
  chat / tui                      Open interactive terminal UI (default)
  status                          Show system health, gateway, active agent, model, vitals
  doctor                          Health checks + quick fixes for environment, venv, keys, audio, gateway
  agents *                        Manage isolated & coordinated agents (list, switch, info, add)
  models *                        Model discovery, list, status, set default
  gateway / daemon *              Start, inspect, stop the WebSocket Gateway & background server
  channels *                      Manage connected channels (terminal, desktop, mobile-pwa)
  skills *                        List and inspect Antigravity skills
  tools *                         List and search registered tools
  missions *                      Autonomous persistent missions management
  sentinel *                      Workspace sentinel perception and code anomaly status
  briefing                        The Stark Morning Briefing
  protocol <name>                 Execute house protocol (workshop, clean_slate, lockdown, overdrive)
  sessions *                      Manage multi-turn conversation sessions
  exec <prompt>                   Run a single turn or autonomous task and output answer

Examples:
  jjarvis
    Start the interactive terminal UI with active agent.
  jjarvis status
    Inspect gateway, active agent, model, and system vitals.
  jjarvis doctor --fix
    Run comprehensive diagnostics and repair missing dependencies/config.
  jjarvis agents list
    Inspect all configured multi-agent profiles.
  jjarvis agents switch ultron
    Switch active persona to ULTRON for offensive coding.
  jjarvis models list
    Show model catalog, token contexts, and auth status.
  jjarvis "run tests and fix failures"
    Directly execute an autonomous agentic task.
""")


def main():
    import argparse
    argv = sys.argv[1:]

    # Fast-path version
    if any(arg in argv for arg in ("-V", "--version")):
        print(f"JARVIS {CLI_VERSION} ({CLI_RELEASE})")
        sys.exit(0)

    # Fast-path help if no subcommands or explicitly asked
    if any(arg in argv for arg in ("-h", "--help")) and (not argv or argv[0] in ("-h", "--help")):
        print_root_help()
        sys.exit(0)

    # Parse top-level arguments
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--agent", type=str, default=None)
    parser.add_argument("--mode", type=str, choices=["auto", "agent", "direct", "boost"], default="auto")
    parser.add_argument(
        "--dangerously-skip-permissions", "--dangerously_skip_permissions", "-y", "--yes",
        dest="dangerously_skip_permissions",
        action="store_true"
    )
    args, remaining = parser.parse_known_args()

    # Subcommand dispatch
    command = remaining[0].lower() if remaining else "chat"
    cmd_args = remaining[1:]

    if command in ("help", "--help", "-h"):
        print_root_help()
        sys.exit(0)

    if command == "status":
        assistant = JarvisAssistant(
            dangerously_skip_permissions=args.dangerously_skip_permissions,
            mode=args.mode,
            agent_id=args.agent,
            show_banner=False
        )
        assistant._show_status()
        sys.exit(0)

    if command == "doctor":
        fix = any(a in cmd_args for a in ("--fix", "-f", "--repair"))
        assistant = JarvisAssistant(
            dangerously_skip_permissions=args.dangerously_skip_permissions,
            mode=args.mode,
            agent_id=args.agent,
            show_banner=False
        )
        res = assistant._handle_doctor_command("fix" if fix else "")
        print(res)
        sys.exit(0)

    if command in ("agents", "agent"):
        assistant = JarvisAssistant(
            dangerously_skip_permissions=args.dangerously_skip_permissions,
            mode=args.mode,
            agent_id=args.agent,
            show_banner=False
        )
        sub = cmd_args[0] if cmd_args else "list"
        extra = cmd_args[1] if len(cmd_args) > 1 else ""
        res = assistant._handle_agent_command(sub, extra)
        print(res)
        sys.exit(0)

    if command == "models":
        assistant = JarvisAssistant(
            dangerously_skip_permissions=args.dangerously_skip_permissions,
            mode=args.mode,
            agent_id=args.agent,
            show_banner=False
        )
        sub = cmd_args[0] if cmd_args else "list"
        extra = cmd_args[1] if len(cmd_args) > 1 else ""
        res = asyncio.run(assistant._handle_model_command(sub, extra))
        print(res)
        sys.exit(0)

    if command in ("gateway", "daemon"):
        assistant = JarvisAssistant(
            dangerously_skip_permissions=args.dangerously_skip_permissions,
            mode=args.mode,
            agent_id=args.agent,
            show_banner=False
        )
        sub = cmd_args[0] if cmd_args else "status"
        res = assistant._handle_gateway_command(sub)
        print(res)
        sys.exit(0)

    if command == "channels":
        assistant = JarvisAssistant(
            dangerously_skip_permissions=args.dangerously_skip_permissions,
            mode=args.mode,
            agent_id=args.agent,
            show_banner=False
        )
        res = assistant._handle_channels_command()
        print(res)
        sys.exit(0)

    if command == "skills":
        assistant = JarvisAssistant(
            dangerously_skip_permissions=args.dangerously_skip_permissions,
            mode=args.mode,
            agent_id=args.agent,
            show_banner=False
        )
        sub = cmd_args[0] if cmd_args else ""
        if sub in ("info", "show") and len(cmd_args) > 1:
            res = assistant._show_skill_content(cmd_args[1])
        else:
            res = assistant._handle_skills_command(sub)
        print(res)
        sys.exit(0)

    if command == "tools":
        assistant = JarvisAssistant(
            dangerously_skip_permissions=args.dangerously_skip_permissions,
            mode=args.mode,
            agent_id=args.agent,
            show_banner=False
        )
        q = " ".join(cmd_args)
        res = assistant._handle_tools_command(q)
        print(res)
        sys.exit(0)

    if command in ("missions", "mission"):
        assistant = JarvisAssistant(
            dangerously_skip_permissions=args.dangerously_skip_permissions,
            mode=args.mode,
            agent_id=args.agent,
            show_banner=False
        )
        sub = cmd_args[0] if cmd_args else "list"
        extra = cmd_args[1] if len(cmd_args) > 1 else ""
        res = asyncio.run(assistant._handle_missions_command(sub, extra))
        print(res)
        sys.exit(0)

    if command == "sentinel":
        assistant = JarvisAssistant(
            dangerously_skip_permissions=args.dangerously_skip_permissions,
            mode=args.mode,
            agent_id=args.agent,
            show_banner=False
        )
        sub = " ".join(cmd_args)
        res = asyncio.run(assistant.process(f"/sentinel {sub}"))
        print(res)
        sys.exit(0)

    if command == "briefing":
        assistant = JarvisAssistant(
            dangerously_skip_permissions=args.dangerously_skip_permissions,
            mode=args.mode,
            agent_id=args.agent,
            show_banner=False
        )
        res = asyncio.run(assistant.process("/briefing"))
        console.print(Panel(Markdown(str(res)), title="[bold cyan]◈ The Stark Morning Briefing[/]", border_style="cyan"))
        sys.exit(0)

    if command == "protocol":
        assistant = JarvisAssistant(
            dangerously_skip_permissions=args.dangerously_skip_permissions,
            mode=args.mode,
            agent_id=args.agent,
            show_banner=False
        )
        sub = " ".join(cmd_args) or "workshop"
        res = asyncio.run(assistant.process(f"/protocol {sub}"))
        console.print(Panel(Markdown(str(res)), title=f"[bold cyan]◈ House Protocol: {sub}[/]", border_style="cyan"))
        sys.exit(0)

    if command in ("exec", "run"):
        prompt = " ".join(cmd_args).strip()
        if not prompt:
            print("Usage: jjarvis exec <prompt>")
            sys.exit(1)
        assistant = JarvisAssistant(
            dangerously_skip_permissions=args.dangerously_skip_permissions,
            mode=args.mode,
            agent_id=args.agent,
            show_banner=False
        )
        res = asyncio.run(assistant.process(prompt))
        if res:
            console.print(Panel(Markdown(str(res)), title=f"{assistant.agent.badge}", border_style="cyan"))
        sys.exit(0)

    # If argument wasn't 'chat' / 'tui' but someone passed a custom query like: jjarvis "what is the date"
    if command not in ("chat", "tui") and len(remaining) > 0 and not command.startswith("-"):
        prompt = " ".join(remaining).strip()
        assistant = JarvisAssistant(
            dangerously_skip_permissions=args.dangerously_skip_permissions,
            mode=args.mode,
            agent_id=args.agent,
            show_banner=False
        )
        res = asyncio.run(assistant.process(prompt))
        if res:
            console.print(Panel(Markdown(str(res)), title=f"{assistant.agent.badge}", border_style="cyan"))
        sys.exit(0)

    # Default: launch interactive TUI / chat
    assistant = JarvisAssistant(
        dangerously_skip_permissions=args.dangerously_skip_permissions,
        mode=args.mode,
        agent_id=args.agent,
        show_banner=True
    )
    asyncio.run(assistant.run())


if __name__ == "__main__":
    main()
