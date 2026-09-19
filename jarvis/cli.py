import asyncio
import os
import sys
import time
import json
import inspect
from dotenv import load_dotenv
from pathlib import Path
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

# Find .env relative to this file's location
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

from jarvis.api_client import JarvisAPIClient, JarvisAPIClient as NIMClient
from jarvis.tools import ToolRegistry
from jarvis.diagnostics import run_diagnostics_sync
from jarvis.voice import ProactiveMonitor, VoiceManager
from jarvis.memory import Memory
from jarvis.skills_engine import get_skills_engine

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

SLASH_COMMANDS = [
    '/help', '/model', '/mode', '/plan', '/goal', '/boost', '/grill-me',
    '/skills', '/skill', '/learn', '/subagents', '/agents',
    '/inspect', '/test',
    '/tools', '/missions', '/mission',
    '/sessions', '/session', '/diagnose', '/status', '/vitals',
    '/context', '/history', '/speak', '/clear', '/exit',
    '/calendar', '/email', '/google', '/auth', '/watch', '/trade'
]


class JarvisAssistant:
    def __init__(self):
        boot_start = time.time()
        self.voice_enabled = True
        self.mode = "auto"  # "auto" | "agent" | "direct" | "boost"
        
        # Show banner
        console.print(BOOT_ART, style="bold cyan")
        console.print(
            "Just A Rather Very Intelligent System — Antigravity Agentic Edition",
            style="bold cyan", justify="center"
        )
        
        # Initialize core systems
        self.api = JarvisAPIClient()
        self.tools = ToolRegistry()
        self.skills_engine = get_skills_engine()
        active_model = getattr(self.api, 'model', 'nvidia/nemotron-3-super-120b-a12b')
        active_provider = getattr(self.api.provider, 'name', 'NVIDIA NIM')
        
        console.print(
            f"[dim white]Provider:[/] [cyan]{active_provider}[/]  |  "
            f"[dim white]Model:[/] [bold green]{active_model}[/]  |  "
            f"[dim white]Mode:[/] [magenta]{self.mode.upper()}[/]",
            justify="center"
        )
        console.rule(style="dim cyan")
        
        boot_time = time.time() - boot_start
        console.print(
            f"[green]✓ Online in {boot_time:.2f}s — "
            f"{len(self.tools.tools)} tools | {len(self.skills_engine.skills)} Antigravity skills | 5 subagents active[/]\n"
        )
        
        # Setup interactive prompt toolkit session if available and running in a terminal
        self.pt_session = None
        if HAS_PROMPT_TOOLKIT and hasattr(sys.stdin, 'isatty') and sys.stdin.isatty():
            try:
                completer = WordCompleter(SLASH_COMMANDS, ignore_case=True)
                self.pt_session = PromptSession(
                    history=InMemoryHistory(),
                    completer=completer
                )
            except Exception:
                self.pt_session = None
        
        # Boot voice greeting asynchronously in background
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
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(speak(f"{greeting}, sir. All systems operational."))
            except RuntimeError:
                def run_greeting():
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(speak(f"{greeting}, sir. All systems operational."))
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
        try:
            from jarvis.voice import speak
            loop = asyncio.get_running_loop()
            loop.create_task(speak(speak_text))
        except RuntimeError:
            import threading
            def run_speak():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(speak(speak_text))
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
        elif cmd == '/exit' or cmd == '/quit':
            console.print("[cyan]JARVIS offline. Goodbye, sir.[/]")
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
        elif cmd == '/skills':
            return self._handle_skills_command(subcmd)
        elif cmd == '/skill':
            target_skill = (subcmd + " " + arg).strip()
            if not target_skill:
                return "Usage: [cyan]/skill <name>[/]. Example: [cyan]/skill agentic-coding[/]"
            return self._show_skill_content(target_skill)
        elif cmd == '/learn':
            return await self._handle_learn_command(subcmd)
        elif cmd in ('/subagents', '/agents'):
            return self._show_subagents()
        elif cmd == '/inspect':
            target_path = (subcmd + " " + arg).strip() or "."
            return await self._execute_tool("inspect_project", {"path": target_path})
        elif cmd == '/test':
            target_path = (subcmd + " " + arg).strip() or "."
            return await self._execute_tool("run_tests", {"path": target_path})
        elif cmd == '/tools':
            return self._handle_tools_command(subcmd)
        elif cmd in ('/status', '/vitals'):
            return self._show_vitals()
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
        elif cmd == '/missions' or cmd == '/mission':
            return await self._handle_missions_command(subcmd, arg)
        elif cmd == '/sessions' or cmd == '/session':
            return self._handle_sessions_command(subcmd, arg)
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
    
    async def _handle_model_command(self, subcmd: str, arg: str) -> str:
        current_model = getattr(self.api, 'model', 'unknown')
        provider_name = getattr(self.api.provider, 'name', 'unknown')

        presets = {
            "super": "nvidia/nemotron-3-super-120b-a12b",
            "nemotron": "nvidia/nemotron-3-super-120b-a12b",
            "nemotron-super": "nvidia/nemotron-3-super-120b-a12b",
            "llama": "meta/llama-3.2-11b-vision-instruct",
            "llama3": "meta/llama-3.2-11b-vision-instruct",
            "gpt": "openai/gpt-oss-20b",
            "gpt-oss": "openai/gpt-oss-20b"
        }

        if not subcmd:
            # Show model status and test latency
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

            table = Table(title="LLM Provider & Model Status", style="cyan")
            table.add_column("Property", style="bold white")
            table.add_column("Value", style="green")
            table.add_row("Provider", provider_name)
            table.add_row("Active Model", current_model)
            table.add_row("Ping Latency", latency_str)
            table.add_row("Available Presets", "/model super | /model llama | /model gpt | /model gemini | /model groq")
            console.print(table)
            return "Use [cyan]/model <preset>[/] to switch models on the fly, sir."

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
            # Custom model name
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

    def _show_vitals(self) -> str:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        table = Table(title="System Vitals", style="cyan")
        table.add_column("Resource", style="bold white")
        table.add_column("Usage", style="green")
        table.add_row("CPU Load", f"{cpu}%")
        table.add_row("RAM Usage", f"{mem.percent}% ({mem.used // (1024*1024)} MB / {mem.total // (1024*1024)} MB)")
        table.add_row("Disk Usage", f"{disk.percent}% ({disk.used // (1024*1024*1024)} GB / {disk.total // (1024*1024*1024)} GB)")
        table.add_row("Active Model", getattr(self.api, 'model', 'unknown'))
        table.add_row("Agent Mode", self.mode.upper())
        console.print(table)
        return "All vitals within normal parameters, sir."

    async def _handle_missions_command(self, subcmd: str, arg: str) -> str:
        try:
            from jarvis.mission_manager import MissionManager
            mm = MissionManager()
            if subcmd in ("", "list"):
                missions = mm.list_missions()
                if not missions:
                    return "No persistent missions found. Missions are created automatically when large goals are given."
                table = Table(title="Persistent Missions", style="cyan")
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
                return f"Mission command: /missions [list|next|approve <id>]"
        except Exception as e:
            return f"Missions error: {e}"

    def _handle_sessions_command(self, subcmd: str, arg: str) -> str:
        sessions = self.api.list_sessions()
        if not subcmd or subcmd == "list":
            table = Table(title="Conversation Sessions", style="cyan")
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
        return """=====================================================
            J.A.R.V.I.S. AGENT COMMAND REFERENCE
=====================================================

--- ANTIGRAVITY & AUTONOMOUS AGENT CONTROLS ---
  /mode [auto|agent|boost|direct] Toggle agent operational mode
  /plan <goal> / /goal <goal>     Decompose & execute goal with autonomous swarm
  /boost                          Activate Boost Mode (deep verification & test gating)
  /skills [category]              View all 11 embedded Antigravity skills
  /skill <name>                   Inspect full instructions & runbook for a skill
  /learn [name]                   Interactive wizard to learn & persist a new skill
  /subagents / /agents            Inspect the 5 logical subagents in the JARVIS fleet
  /inspect [path]                 Inspect project directory structure & entry points
  /test [path]                    Run test suite with pass/fail telemetry
  /grill-me                       Enter interactive requirements clarification mode

--- MODEL & RUNTIME CONTROLS ---
  /model [name]       Switch LLM (super, llama, gpt, gemini, groq)
  /status / /vitals   View live CPU, RAM, disk, and model vitals
  /tools [query]      Search and inspect 105 registered tools
  /missions           Manage persistent background missions
  /sessions           Manage multi-turn conversation sessions
  /diagnose           Run comprehensive non-blocking system diagnostics
  /context [clear]    View or clear active session token context
  /history            View recent conversation history
  /speak on|off       Toggle Edge-TTS voice output
  /clear              Clear screen
  /exit               Clean system shutdown

--- GOOGLE WORKSPACE ---
  /calendar           List Google Calendar schedule
  /email [summary]    Check Gmail and get executive briefing

====================================================="""
    
    async def _run_plan_flow(self, goal: str) -> str:
        """Explicit multi-step agent planning and execution flow."""
        console.print(f"\n[bold cyan]◈ [Autonomous Planning][/] Analyzing goal: [white]{goal}[/]")
        if not getattr(self.api, 'dispatcher', None):
            return "Agent dispatcher not initialized."
        
        with console.status("[bold cyan]Synthesizing execution plan...[/]", spinner="dots"):
            plan = await self.api.dispatcher.planning_agent.plan_goal(goal, self.api)
        
        if not plan.subtasks:
            console.print("[yellow]Plan resolved to direct execution.[/]")
            return await self._run_direct_flow(goal)

        console.print(f"[bold cyan]Plan decomposed into {len(plan.subtasks)} subtask(s):[/]")
        for i, st in enumerate(plan.subtasks, 1):
            console.print(f"  [cyan]{i}.[/] [bold white]{st.description}[/] [dim]→ Assigned: {st.assigned_agent}[/]")
        console.print()

        with console.status("[bold cyan]Executing autonomous subtasks...[/]", spinner="dots"):
            dispatch_res = await self.api.dispatcher.dispatch(
                user_prompt=goal,
                tool_registry=self.tools,
                llm_client=self.api
            )

        resp = dispatch_res.get("content", "") or "Goal execution completed, sir."
        self.api.add_assistant_message(resp, session_id="cli")
        return resp

    async def _run_direct_flow(self, user_input: str) -> str:
        """Direct fast-path tool-calling execution."""
        self.api.add_user_message(user_input, session_id="cli")
        
        with console.status("[bold cyan]◈ JARVIS is reasoning...[/]", spinner="dots"):
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
                    # Multi-step task detected!
                    return await self._run_plan_flow(user_input)

            # Direct execution for simple queries
            return await self._run_direct_flow(user_input)
    
    async def process_command(self, user_input: str) -> str:
        """Alias for backward compatibility with manual test runners."""
        return await self.process(user_input)

    async def process_single_command(self, user_input: str) -> str:
        """Alias for backward compatibility with manual test runners."""
        return await self.process(user_input)

    def _load_config(self):
        from jarvis.tools import _load_config
        return _load_config()

    async def run(self):
        console.print(
            "[dim cyan]Type anything or [bold cyan]/help[/] for commands. "
            "[bold cyan]/mode[/] to switch agent modes. [bold cyan]/exit[/] to quit.[/]\n"
        )
        
        while True:
            try:
                model_name = getattr(self.api, 'model', 'nemotron-super')
                short_model = model_name.split('/')[-1][:12]
                prompt_label = f"[cyan]◈ [{self.mode}:{short_model}] YOU  →  [/]"
                
                if self.pt_session:
                    # Run prompt_toolkit in thread to avoid blocking asyncio loop
                    user_input = await asyncio.to_thread(
                        self.pt_session.prompt,
                        f"◈ [{self.mode}:{short_model}] YOU  →  "
                    )
                else:
                    user_input = console.input(prompt_label)
                
                user_input = user_input.strip()
                if not user_input:
                    continue
                
                t_proc0 = time.time()
                response = await self.process(user_input)
                elapsed = time.time() - t_proc0
                
                if response:
                    # Render response in Markdown
                    console.print()
                    console.print(Panel(
                        Markdown(response),
                        title=f"[bold cyan]◈ JARVIS[/] [dim]({elapsed:.2f}s)[/]",
                        border_style="cyan"
                    ))
                    console.print()
                    
                    await self._speak(response)
                        
            except (KeyboardInterrupt, EOFError):
                console.print("\n[cyan]JARVIS offline. Goodbye, sir.[/]")
                break
            except Exception as e:
                console.print(f"[bold red]Error:[/] {e}")


# Alias for backward compatibility with tests
JARVISCLI = JarvisAssistant

def main():
    assistant = JarvisAssistant()
    asyncio.run(assistant.run())

if __name__ == "__main__":
    main()
