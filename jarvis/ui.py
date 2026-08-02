"""
HUD / Sci-Fi UI Module for JARVIS
Handles rich terminal rendering, ASCII banner, panel wrappers, state management, and real-time audio animations.
"""

import sys
from enum import Enum
import time
from typing import Callable
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


class UIState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    EXECUTING = "EXECUTING"


class UIManager:
    """Manages HUD terminal aesthetics and live status animations for JARVIS"""
    
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
        """Get the current state"""
        return self.state

    def get_status_badge(self) -> str:
        """Return styled status indicator badge line"""
        if self.state == UIState.IDLE:
            return "[bold cyan]● STATE:[/bold cyan] [dim cyan]IDLE[/dim cyan]"
        elif self.state == UIState.LISTENING:
            return "[bold cyan]● STATE:[/bold cyan] [bold bright_cyan]🎤 LISTENING[/bold bright_cyan]"
        elif self.state == UIState.THINKING:
            return "[bold cyan]● STATE:[/bold cyan] [bold cyan]🧠 THINKING[/bold cyan]"
        elif self.state == UIState.SPEAKING:
            return "[bold cyan]● STATE:[/bold cyan] [bold bright_cyan]🔊 SPEAKING[/bold bright_cyan]"
        elif self.state == UIState.EXECUTING:
            return "[bold cyan]● STATE:[/bold cyan] [bold yellow]⚡ EXECUTING[/bold yellow]"
        return "[bold cyan]● STATE:[/bold cyan] [dim cyan]IDLE[/dim cyan]"

    def show_banner(self):
        """Display sci-fi HUD startup banner once on launch"""
        banner_art = """[bold bright_cyan]
    ███████╗.█████╗ .██████╗.██╗   ██╗██╗.███████╗
    ╚══███╔╝██╔══██╗██╔══██╗██║   ██║██║██╔════╝
      ███╔╝ ███████║██████╔╝██║   ██║██║███████╗
     ███╔╝  ██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
    ███████╗██║  ██║██║  ██║ ╚████╔╝ ██║███████║
    ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═════╝  ╚═╝╚══════╝
[/bold bright_cyan]
[bold white]  J.A.R.V.I.S. // TACTICAL HUD TERMINAL INTERFACE[/bold white]
[dim cyan]  Powered by NVIDIA NIM API | Type [bold white]/help[/bold white] for commands, [bold white]/exit[/bold white] to quit[/dim cyan]"""

        panel = Panel(
            banner_art,
            border_style="cyan",
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
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2)
        )
        self.console.print(panel)

    def render_tool_exec(self, message: str):
        """Print tool call with dimmed cyan prefix and icon"""
        self.console.print(f"[dim bright_cyan][EXEC][/dim bright_cyan] [dim white]{message}[/dim white]")

    def get_user_input(self, prompt_text: str = "") -> str:
        """Get user input with HUD prompt symbol and visually separate user vs JARVIS text"""
        prompt_symbol = "[bold green]>[/bold green] "
        try:
            return Prompt.ask(prompt_symbol, default="", show_default=False)
        except Exception:
            return input("> ")

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
