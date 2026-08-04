"""
OpenClaw Skills Bridge for JARVIS
Exposes OpenClaw skills as callable JARVIS tools via the openclaw CLI (npx) and GitHub CLI (gh).
"""

import asyncio
import shutil
from typing import List, Any, Optional, Dict
from pathlib import Path

from jarvis.tools import Tool, ToolRegistry


def _get_npx_path() -> str:
    """Resolve system path to npx executable."""
    which_npx = shutil.which("npx.cmd") or shutil.which("npx")
    if which_npx:
        return which_npx
    default_win = r"C:\Program Files\nodejs\npx.cmd"
    if Path(default_win).exists():
        return default_win
    return "npx"


def _get_gh_path() -> str:
    """Resolve system path to gh executable."""
    which_gh = shutil.which("gh.exe") or shutil.which("gh")
    if which_gh:
        return which_gh
    default_win = r"C:\Program Files\GitHub CLI\gh.exe"
    if Path(default_win).exists():
        return default_win
    return "gh"


async def _run_openclaw(cmd_args: List[str], timeout: int = 60) -> str:
    """Run openclaw via npx and return output."""
    npx_path = _get_npx_path()
    cmd = [npx_path, "-y", "openclaw"] + cmd_args
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path.home())
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode == 0:
            return stdout.decode('utf-8', errors='replace').strip() or "Command executed successfully"
        else:
            return f"Error (exit {proc.returncode}): {stderr.decode('utf-8', errors='replace').strip()}"
    except asyncio.TimeoutError:
        return f"Error: Command timed out after {timeout}s"
    except FileNotFoundError:
        return "Error: 'npx' not found. Install Node.js and ensure openclaw is installed globally (npm i -g openclaw)"
    except Exception as e:
        return f"Error: {str(e)}"


class OpenClawSkillRegistryTool(Tool):
    """Tool to list and inspect available OpenClaw skills"""
    
    def __init__(self):
        super().__init__("openclaw_skills", "List, inspect, and search OpenClaw skills")
    
    async def execute(self, action: str = "list", skill_name: str = "", query: str = "", **kwargs) -> str:
        s_name = skill_name or kwargs.get("skill") or kwargs.get("name")
        q_str = query or kwargs.get("q")
        
        if action == "list":
            cmd = ["skills", "list"]
        elif action in ["inspect", "info"] and s_name:
            cmd = ["skills", "info", s_name]
        elif action == "search" and q_str:
            cmd = ["skills", "search", q_str]
        else:
            cmd = ["skills", "list"]
        
        return await _run_openclaw(cmd)


class OpenClawGitHubTool(Tool):
    """GitHub operations via gh CLI directly"""
    
    def __init__(self, default_repo: str = "nivedjkr/jarvis-assistant"):
        super().__init__(
            "openclaw_github",
            "GitHub CLI for issues, PRs, CI/check logs, comments, reviews, releases, repos, and gh api queries"
        )
        self.default_repo = default_repo
        try:
            import yaml
            if Path("config.yaml").exists():
                with open("config.yaml", "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    self.default_repo = cfg.get("github", {}).get("default_repo", default_repo)
        except Exception:
            pass
    
    async def execute(
        self,
        command: str = "",
        subcommand: str = "",
        repo: str = "",
        action: str = "",
        **kwargs
    ) -> str:
        target_repo = repo or self.default_repo
        kw = dict(kwargs)
        
        # Pop action if passed in kwargs or parameter
        act = (action or kw.pop("action", "")).strip()
        
        # Parse action into command/subcommand if command is not explicitly set
        if act and not command:
            act_lower = act.lower()
            if act_lower in ("list", "issues", "issue_list", "issue-list"):
                command, subcommand = "issue", "list"
            elif act_lower in ("prs", "pulls", "pr_list", "pr-list"):
                command, subcommand = "pr", "list"
            elif act_lower in ("status", "pr_status"):
                command, subcommand = "pr", "status"
            elif act_lower in ("create", "issue_create"):
                command, subcommand = "issue", "create"
            elif act_lower in ("pr_create",):
                command, subcommand = "pr", "create"
            elif act_lower in ("repo", "repo_view", "repo-view"):
                command, subcommand = "repo", "view"
            elif act_lower in ("repo_list", "repo-list"):
                command, subcommand = "repo", "list"
            elif act_lower == "api":
                command = "api"
            else:
                parts = act.split()
                command = parts[0]
                if len(parts) > 1:
                    subcommand = parts[1]
                if len(parts) > 2:
                    pos_args = parts[2:]
                    for idx, pa in enumerate(pos_args):
                        kw[f"_pos_{idx}"] = pa

        # Default fallback command if still empty
        if not command:
            command = "issue"
            subcommand = "list"

        gh_path = _get_gh_path()
        cmd = [gh_path, command]

        # Commands that accept --repo flag
        repo_scoped_commands = {
            "issue", "pr", "run", "workflow", "release",
            "project", "gist", "secret", "variable", "search"
        }

        # Handling specific command structures
        if command == "api":
            endpoint = subcommand or f"repos/{target_repo}"
            cmd.append(endpoint)
        elif command == "repo":
            sub = subcommand or "view"
            cmd.append(sub)
            if sub in ("view", "clone", "fork", "sync"):
                # Pass repo positionally for gh repo view/clone
                pos_repo = kw.pop("name", None) or target_repo
                if pos_repo:
                    cmd.append(pos_repo)
            elif sub == "list" and target_repo:
                owner = target_repo.split("/")[0] if "/" in target_repo else target_repo
                cmd.append(owner)
        else:
            if subcommand:
                cmd.append(subcommand)
            
            # Extract positional ID/number argument for commands like issue view/close/comment, pr view/checkout
            if command in ("issue", "pr") and subcommand in ("view", "close", "reopen", "comment", "checkout", "diff", "merge", "edit", "lock"):
                num_val = kw.pop("number", None) or kw.pop("issue_number", None) or kw.pop("pr_number", None) or kw.pop("id", None)
                if num_val is not None:
                    cmd.append(str(num_val))

            if command == "issue" and subcommand == "create" and "body" not in kw:
                kw["body"] = ""

            if target_repo and command in repo_scoped_commands:
                cmd.extend(["--repo", target_repo])

        # Append remaining kwargs as flags
        pos_keys = sorted([k for k in kw.keys() if k.startswith("_pos_")])
        for pk in pos_keys:
            cmd.append(str(kw.pop(pk)))

        for k, v in list(kw.items()):
            if v is None or k.startswith("_") or k in ("command", "subcommand", "repo"):
                continue
            flag_name = k.replace("_", "-")
            if isinstance(v, bool):
                if v:
                    cmd.append(f"--{flag_name}")
            else:
                cmd.extend([f"--{flag_name}", str(v)])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            out_str = stdout.decode('utf-8', errors='replace').strip()
            err_str = stderr.decode('utf-8', errors='replace').strip()
            if proc.returncode == 0:
                return out_str or "Command executed successfully"
            else:
                return f"Error (exit {proc.returncode}): {err_str or out_str}"
        except asyncio.TimeoutError:
            return "Error: Command timed out after 60s"
        except FileNotFoundError:
            return "Error: 'gh' not found. Install GitHub CLI."
        except Exception as e:
            return f"Error: {str(e)}"


class OpenClawNotionTool(Tool):
    """Notion operations via OpenClaw notion skill"""
    
    def __init__(self):
        super().__init__(
            "openclaw_notion",
            "Notion CLI/API for pages, Markdown content, data sources, files, comments, search, Workers, and raw API calls"
        )
    
    async def execute(self, action: str = "pages", **kwargs) -> str:
        cmd = ["skills", "run", "notion"]
        if action:
            cmd.append(action)
        for key, value in kwargs.items():
            if value is not None:
                cmd.extend([f"--{key.replace('_', '-')}", str(value)])
        return await _run_openclaw(cmd)


class OpenClawBrowserTool(Tool):
    """Browser automation via OpenClaw browser-automation skill"""
    
    def __init__(self):
        super().__init__(
            "openclaw_browser_automation",
            "Control web pages with the OpenClaw browser tool: multi-step flows, login checks, tab management, recovery from stale refs/timeouts"
        )
    
    async def execute(self, action: str = "navigate", url: str = "", **kwargs) -> str:
        cmd = ["skills", "run", "browser-automation"]
        if action:
            cmd.append(action)
        if url:
            cmd.extend(["--url", url])
        for key, value in kwargs.items():
            if value is not None:
                cmd.extend([f"--{key.replace('_', '-')}", str(value)])
        return await _run_openclaw(cmd, timeout=120)


class OpenClawDiagramTool(Tool):
    """Diagram creation via OpenClaw diagram-maker skill"""
    
    def __init__(self):
        super().__init__(
            "openclaw_diagram_maker",
            "Create SVG/HTML or Excalidraw diagrams for concepts, architecture, flows, and whiteboards"
        )
    
    async def execute(self, action: str = "create", **kwargs) -> str:
        cmd = ["skills", "run", "diagram-maker"]
        if action:
            cmd.append(action)
        for key, value in kwargs.items():
            if value is not None:
                cmd.extend([f"--{key.replace('_', '-')}", str(value)])
        return await _run_openclaw(cmd)


class OpenClawWeatherTool(Tool):
    """Weather via wttr.in API (no OpenClaw dependency)"""
    
    def __init__(self):
        super().__init__(
            "openclaw_weather",
            "Current weather and forecasts via wttr.in. Use location parameter."
        )
    
    async def execute(self, location: str = "", city: str = "", query: str = "", **kwargs) -> str:
        loc = location or city or query or kwargs.get("place") or kwargs.get("q") or "auto"
        import aiohttp
        try:
            url = f"https://wttr.in/{loc}?format=j1"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        import json
                        data = json.loads(text)
                        current = data.get('current_condition', [{}])[0]
                        area = data.get('nearest_area', [{}])[0]
                        area_name = area.get('areaName', [{}])[0].get('value', loc)
                        country = area.get('country', [{}])[0].get('value', '')
                        
                        temp_c = current.get('temp_C', 'N/A')
                        temp_f = current.get('temp_F', 'N/A')
                        condition = current.get('weatherDesc', [{}])[0].get('value', 'N/A')
                        feels_like_c = current.get('FeelsLikeC', 'N/A')
                        humidity = current.get('humidity', 'N/A')
                        wind_kmph = current.get('windspeedKmph', 'N/A')
                        precip_mm = current.get('precipMM', 'N/A')
                        
                        return (f"Weather for {area_name}, {country}:\n"
                                f"Temperature: {temp_c}°C / {temp_f}°F (feels like {feels_like_c}°C)\n"
                                f"Condition: {condition}\n"
                                f"Humidity: {humidity}%\n"
                                f"Wind: {wind_kmph} km/h\n"
                                f"Precipitation: {precip_mm} mm")
                    else:
                        return f"Error: wttr.in returned {resp.status}"
        except Exception as e:
            return f"Error fetching weather: {str(e)}"


class OpenClawHealthCheckTool(Tool):
    """Health check via OpenClaw healthcheck skill"""
    
    def __init__(self):
        super().__init__(
            "openclaw_healthcheck",
            "Audit/harden OpenClaw hosts: SSH, firewall, updates, exposure, backups, disk encryption, gateway security"
        )
    
    async def execute(self, action: str = "audit", **kwargs) -> str:
        cmd = ["skills", "run", "healthcheck"]
        if action:
            cmd.append(action)
        for key, value in kwargs.items():
            if value is not None:
                cmd.extend([f"--{key.replace('_', '-')}", str(value)])
        return await _run_openclaw(cmd, timeout=120)


class OpenClawNodeConnectTool(Tool):
    """Node connection diagnostics via OpenClaw node-connect skill"""
    
    def __init__(self):
        super().__init__(
            "openclaw_node_connect",
            "Diagnose OpenClaw Android, iOS, or macOS node pairing, QR/setup code, route, auth, and connection failures"
        )
    
    async def execute(self, action: str = "diagnose", **kwargs) -> str:
        cmd = ["skills", "run", "node-connect"]
        if action:
            cmd.append(action)
        for key, value in kwargs.items():
            if value is not None:
                cmd.extend([f"--{key.replace('_', '-')}", str(value)])
        return await _run_openclaw(cmd)


class OpenClawTaskFlowTool(Tool):
    """TaskFlow orchestration via OpenClaw taskflow skill"""
    
    def __init__(self):
        super().__init__(
            "openclaw_taskflow",
            "Coordinate multi-step detached tasks as one durable TaskFlow job with owner context, state, waits, and child tasks"
        )
    
    async def execute(self, action: str = "list", **kwargs) -> str:
        cmd = ["skills", "run", "taskflow"]
        if action:
            cmd.append(action)
        for key, value in kwargs.items():
            if value is not None:
                cmd.extend([f"--{key.replace('_', '-')}", str(value)])
        return await _run_openclaw(cmd)


class OpenClawGenericSkillTool(Tool):
    """Generic tool to run any OpenClaw skill by name"""
    
    def __init__(self):
        super().__init__("openclaw_skill", "Run any OpenClaw skill by name with arbitrary arguments")
    
    async def execute(self, skill: str = "", action: str = "", **kwargs) -> str:
        if not skill:
            return "Error: 'skill' parameter required"
        
        cmd = ["skills", "run", skill]
        if action:
            cmd.append(action)
        for key, value in kwargs.items():
            if value is not None:
                cmd.extend([f"--{key.replace('_', '-')}", str(value)])
        return await _run_openclaw(cmd, timeout=120)


REGISTERED_SKILLS = [
    "openclaw_skills",
    "openclaw_github",
    "openclaw_notion",
    "openclaw_browser_automation",
    "openclaw_diagram_maker",
    "openclaw_weather",
    "openclaw_healthcheck",
    "openclaw_node_connect",
    "openclaw_taskflow",
    "openclaw_skill",
]

SKILL_MAP: Dict[str, Tool] = {
    "openclaw_skills": OpenClawSkillRegistryTool(),
    "openclaw_github": OpenClawGitHubTool(),
    "openclaw_notion": OpenClawNotionTool(),
    "openclaw_browser_automation": OpenClawBrowserTool(),
    "openclaw_diagram_maker": OpenClawDiagramTool(),
    "openclaw_weather": OpenClawWeatherTool(),
    "openclaw_healthcheck": OpenClawHealthCheckTool(),
    "openclaw_node_connect": OpenClawNodeConnectTool(),
    "openclaw_taskflow": OpenClawTaskFlowTool(),
    "openclaw_skill": OpenClawGenericSkillTool(),
}

test_args = {
    "openclaw_skills": {"action": "list"},
    "openclaw_github": {"action": "issues"},
    "openclaw_notion": {"action": "pages"},
    "openclaw_browser_automation": {"action": "navigate", "url": "https://example.com"},
    "openclaw_diagram_maker": {"action": "create"},
    "openclaw_weather": {"location": "London"},
    "openclaw_healthcheck": {"action": "audit"},
    "openclaw_node_connect": {"action": "diagnose"},
    "openclaw_taskflow": {"action": "list"},
    "openclaw_skill": {"skill": "weather", "location": "London"}
}


def call_skill(skill_name: str, args: dict, timeout: int = 120) -> str:
    """Call an OpenClaw bridge skill by tool name with arguments."""
    tool = SKILL_MAP.get(skill_name)
    if not tool:
        raise ValueError(f"Skill {skill_name} not found in SKILL_MAP")
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, tool.execute(**args))
            return future.result(timeout=timeout)
    else:
        return loop.run_until_complete(tool.execute(**args))


def test_all_skills() -> Dict[str, str]:
    """Test all 10 OpenClaw skill wrappers and return status dict."""
    results = {}
    for skill_name in REGISTERED_SKILLS:
        try:
            result = call_skill(skill_name, test_args[skill_name])
            if isinstance(result, str) and result.startswith("Error"):
                results[skill_name] = f'FAIL: {result}'
            else:
                results[skill_name] = 'OK'
        except Exception as e:
            results[skill_name] = f'FAIL: {e}'
    return results


def register_openclaw_tools(registry: ToolRegistry) -> None:
    """Register all OpenClaw skill tools in JARVIS ToolRegistry"""
    for tool in SKILL_MAP.values():
        registry.register(tool)