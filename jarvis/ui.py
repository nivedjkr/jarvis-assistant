"""
HUD / Sci-Fi UI Module for JARVIS
Handles rich terminal rendering, ASCII banner, panel wrappers, state management, and real-time audio animations.
"""

import sys
from enum import Enum
import time
from datetime import datetime
from typing import Callable, Optional
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.live import Live
from rich.prompt import Prompt
from rich import box

# Ensure UTF-8 console output on Windows
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console()

# --- Design System & Color Palette Constants ---
COLOR_PRIMARY = "bright_cyan"       # Primary Accent: Electric Blue / Cyan (#00D9FF)
COLOR_SECONDARY = "dim white"      # Secondary / Metadata: Gray
COLOR_SUCCESS = "bold green"       # Success / Confirmation
COLOR_WARNING = "bold yellow"      # Warning / Caution
COLOR_ERROR = "bold red"           # Error / Alert
COLOR_BORDER = "cyan"              # Panel Border Style
PROMPT_SYMBOL = "[bold bright_cyan]JARVIS ▸ [/bold bright_cyan]"


class UIState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    EXECUTING = "EXECUTING"


class UIManager:
    """Manages HUD terminal aesthetics, sci-fi panels, and status animations for JARVIS"""
    
    WAVEFORM_FRAMES = [
        "▁ ▃ ▅ ▇ ▅ ▃ ▁",
        "▃ ▅ ▇ ▅ ▃ ▁ ▃",
        "▅ ▇ ▅ ▃ ▁ ▃ ▅",
        "▇ ▅ ▃ ▁ ▃ ▅ ▇",
        "▅ ▃ ▁ ▃ ▅ ▇ ▅",
        "▃ ▁ ▃ ▅ ▇ ▅ ▃",
    ]
    
    PULSE_DOTS = [".  ", ".. ", "...", "   "]
    
    def __init__(self):
        self.console = console
        self.state = UIState.IDLE
        self._banner_shown = False

    def set_state(self, state: UIState | str):
        """Set the current assistant state"""
        if isinstance(state, str):
            try:
                self.state = UIState(state.upper())
            except ValueError:
                self.state = UIState.IDLE
        else:
            self.state = state

    def get_state(self) -> UIState:
        """Get current state"""
        return self.state

    def get_status_badge(self) -> str:
        """Return styled status indicator badge line with timestamp"""
        now = datetime.now().strftime("%H:%M:%S")
        timestamp = f"[dim white][{now}][/dim white]"
        
        if self.state == UIState.IDLE:
            badge = "[bold cyan]● STATE:[/bold cyan] [dim cyan]IDLE[/dim cyan]"
        elif self.state == UIState.LISTENING:
            badge = "[bold cyan]● STATE:[/bold cyan] [bold bright_cyan]🎤 LISTENING[/bold bright_cyan]"
        elif self.state == UIState.THINKING:
            badge = "[bold cyan]● STATE:[/bold cyan] [bold cyan]🧠 THINKING[/bold cyan]"
        elif self.state == UIState.SPEAKING:
            badge = "[bold cyan]● STATE:[/bold cyan] [bold bright_cyan]🔊 SPEAKING[/bold bright_cyan]"
        elif self.state == UIState.EXECUTING:
            badge = "[bold cyan]● STATE:[/bold cyan] [bold yellow]⚡ EXECUTING[/bold yellow]"
        else:
            badge = "[bold cyan]● STATE:[/bold cyan] [dim cyan]IDLE[/dim cyan]"
            
        return f"{timestamp} {badge}"

    def show_banner(self):
        """Display sci-fi HUD startup banner once on launch"""
        banner_art = (
            "[bold bright_cyan]"
            "  ███████╗.█████╗ .██████╗.██╗   ██╗██╗.███████╗\n"
            "  ╚══███╔╝██╔══██╗██╔══██╗██║   ██║██║██╔════╝\n"
            "    ███╔╝ ███████║██████╔╝██║   ██║██║███████╗\n"
            "   ███╔╝  ██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║\n"
            "  ███████╗██║  ██║██║  ██║ ╚████╔╝ ██║███████║\n"
            "  ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═════╝  ╚═╝╚══════╝\n"
            "[/bold bright_cyan]\n"
            "              [dim white]Created by Nived[/dim white]\n"
            "[cyan]──────────────────────────────────────────────────────────[/cyan]\n"
            "  [dim cyan]v1.0[/dim cyan] [cyan]|[/cyan] [dim white]All systems nominal[/dim white] [cyan]|[/cyan] [dim cyan]Type [bold white]/help[/bold white] for commands[/dim cyan]"
        )

        panel = Panel(
            banner_art,
            title="[bold bright_cyan] J . A . R . V . I . S . [/bold bright_cyan]",
            title_align="center",
            border_style=COLOR_BORDER,
            box=box.ROUNDED,
            padding=(1, 2)
        )
        self.console.print(panel)
        self._banner_shown = True

    def render_response(self, text: str):
        """Wrap JARVIS response in a bordered panel with thin cyan border and title"""
        content = Markdown(text) if text else ""
        panel = Panel(
            content,
            title="[bold bright_cyan]JARVIS[/bold bright_cyan]",
            title_align="left",
            border_style=COLOR_BORDER,
            box=box.ROUNDED,
            padding=(1, 2)
        )
        self.console.print(panel)

    def render_tool_exec(self, message: str, tag: str = "EXEC"):
        """Print tool call with dimmed cyan bracketed tag prefix"""
        self.console.print(f"[dim cyan][{tag}][/dim cyan] [dim white]{message}[/dim white]")

    def get_user_input(self, prompt_text: str = "") -> str:
        """Get user input with electric cyan prompt symbol"""
        try:
            return Prompt.ask(PROMPT_SYMBOL, default="", show_default=False)
        except Exception:
            return input("JARVIS ▸ ")

    def animate_speaking(self, check_busy_fn: Callable[[], bool]):
        """
        Runs a Live visual indicator that animates for the EXACT duration audio playback is active.
        """
        self.set_state(UIState.SPEAKING)
        idx = 0
        with Live(console=self.console, refresh_per_second=10, transient=True) as live:
            while check_busy_fn():
                wave = self.WAVEFORM_FRAMES[idx % len(self.WAVEFORM_FRAMES)]
                renderable = f"[bold bright_cyan]🔊 SPEAKING[/bold bright_cyan]  [cyan]{wave}[/cyan]"
                live.update(renderable)
                time.sleep(0.08)
                idx += 1
        self.set_state(UIState.IDLE)

    def animate_listening(self, check_recording_fn: Callable[[], bool]):
        """
        Runs a Live visual indicator while recording mic input.
        """
        self.set_state(UIState.LISTENING)
        idx = 0
        with Live(console=self.console, refresh_per_second=8, transient=True) as live:
            while check_recording_fn():
                dots = self.PULSE_DOTS[idx % len(self.PULSE_DOTS)]
                renderable = f"[bold bright_cyan]🎤 LISTENING{dots}[/bold bright_cyan]"
                live.update(renderable)
                time.sleep(0.12)
                idx += 1
        self.set_state(UIState.IDLE)


# Global UI instance
ui = UIManager()
