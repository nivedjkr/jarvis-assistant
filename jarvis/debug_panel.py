import time
from datetime import datetime
from typing import List, Dict, Any

class DebugPanel:
    def __init__(self):
        self.enabled = False
        self.tool_calls: List[Dict[str, Any]] = []  # last 10
        self.errors: List[Dict[str, Any]] = []      # last 5
        self.session_start = time.time()
        self.request_count = 0
        self.token_estimate = 0
        self.last_response_time = 0.0
        self.avg_response_time = 0.0
        self.response_times: List[float] = []
        self.current_status = "IDLE"
        self.active_session = "cli"
        self.message_count = 0
        self.context_tokens = 0
        self.last_api_latency = 0.0
        self.last_tool_latency = 0.0

    def record_tool_call(
        self, name: str, duration: float, 
        success: bool, result: str = ""):
        self.last_tool_latency = duration
        self.tool_calls.append({
            "name": name,
            "duration": duration,
            "success": success,
            "result": str(result)[:100],
            "timestamp": time.time()
        })
        if len(self.tool_calls) > 10:
            self.tool_calls = self.tool_calls[-10:]
        if not success:
            self.errors.append({
                "tool": name,
                "error": str(result)[:100],
                "time": datetime.now().strftime('%H:%M:%S')
            })
            if len(self.errors) > 5:
                self.errors = self.errors[-5:]

    def record_response(
        self, duration: float, tokens: int = 0, api_latency: float = 0.0):
        self.request_count += 1
        self.token_estimate += tokens
        self.last_response_time = duration
        if api_latency > 0:
            self.last_api_latency = api_latency
        self.response_times.append(duration)
        if len(self.response_times) > 20:
            self.response_times = self.response_times[-20:]
        self.avg_response_time = sum(self.response_times) / len(self.response_times)

    def render(self) -> str:
        uptime = int(time.time() - self.session_start)
        h, m, s = uptime // 3600, (uptime % 3600) // 60, uptime % 60

        lines = [
            f"[cyan]◈ JARVIS DEBUG PANEL[/cyan]",
            f"STATUS: [yellow]{self.current_status}[/]  UPTIME: {h:02d}:{m:02d}:{s:02d}",
            "─" * 45,
            "[cyan]LAST TOOL CALLS[/]"
        ]

        if not self.tool_calls:
            lines.append("  [dim]No tool calls recorded[/dim]")
        else:
            for tc in self.tool_calls[-5:]:
                icon = "✓" if tc['success'] else "✗"
                color = "green" if tc['success'] else "red"
                lines.append(
                    f"  [{color}]{icon}[/] {tc['name']:<22} {tc['duration']:.2f}s"
                )

        lines += [
            "─" * 45,
            f"[cyan]LATENCY[/]",
            f"Last response: {self.last_response_time:.2f}s",
            f"API call: {self.last_api_latency:.2f}s",
            f"Tool execution: {self.last_tool_latency:.2f}s",
            f"Avg (session): {self.avg_response_time:.2f}s",
            "─" * 45,
            f"[cyan]API USAGE (session)[/]",
            f"Requests: {self.request_count}",
            f"Est. tokens: {self.token_estimate:,}",
            f"Tool calls made: {len(self.tool_calls)}",
            f"Tool failures: {len(self.errors)}",
            "─" * 45,
            f"[cyan]ERRORS (last 5)[/]"
        ]

        if not self.errors:
            lines.append("  [dim]None[/dim]")
        else:
            for err in self.errors[-5:]:
                lines.append(
                    f"  [red][{err['time']}] {err['tool']}: {err['error']}[/]"
                )

        lines += [
            "─" * 45,
            f"[cyan]CONTEXT[/]",
            f"Messages in history: {self.message_count}",
            f"Est. context tokens: {self.context_tokens:,}",
            f"Active session: {self.active_session}"
        ]

        return "\n".join(lines)

# Global debug panel instance
debug = DebugPanel()

def run_standalone():
    """Runs rich.Live view when invoked via python -m jarvis.debug_panel"""
    from rich.live import Live
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    debug.enabled = True
    console.print("[dim cyan]Starting JARVIS Live Debug Panel...[/dim cyan]")

    try:
        with Live(console=console, refresh_per_second=1) as live:
            while True:
                rendered_text = debug.render()
                live.update(Panel(rendered_text, border_style="cyan", title="Debug"))
                time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Debug Panel stopped.[/yellow]")

if __name__ == "__main__":
    run_standalone()
