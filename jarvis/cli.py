"""
Clean, robust Command Line Interface (CLI) for JARVIS.
Core chat pipeline driven strictly by LLM tool calling via NVIDIA NIM API.
"""

import os
import sys
import json
import yaml
from dotenv import load_dotenv
from openai import OpenAI
from jarvis.tools import ToolRegistry

load_dotenv()


def load_config(config_path: str = "config.yaml") -> dict:
    """Load config from YAML file."""
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {
        "api": {
            "base_url": "https://integrate.api.nvidia.com/v1",
            "model": "meta/llama-3.1-8b-instruct",
            "temperature": 0.6,
            "max_tokens": 1000
        }
    }


def chat_with_tools(
    client: OpenAI,
    config: dict,
    messages: list,
    registry: ToolRegistry
) -> str:
    """
    Send conversation history and tool schemas to NIM API.
    If tool_calls are present, execute tools via registry, send results back,
    and return the final response text.
    """
    api_config = config.get("api", {})
    model = api_config.get("model", "meta/llama-3.1-8b-instruct")
    temperature = api_config.get("temperature", 0.6)
    max_tokens = api_config.get("max_tokens", 1000)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=registry.schemas,
            temperature=temperature,
            max_tokens=max_tokens
        )
    except Exception as e:
        error_msg = f"API Error: {str(e)}"
        print(f"[ERROR] {error_msg}")
        return error_msg

    response_message = response.choices[0].message
    tool_calls = getattr(response_message, "tool_calls", None)

    if tool_calls:
        messages.append(response_message)

        for tool_call in tool_calls:
            func_name = tool_call.function.name
            try:
                func_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
            except Exception:
                func_args = {}

            tool_result = registry.execute_tool(func_name, func_args)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": func_name,
                "content": str(tool_result)
            })

        try:
            second_response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            final_text = second_response.choices[0].message.content or ""
            messages.append({"role": "assistant", "content": final_text})
            return final_text
        except Exception as e:
            error_msg = f"API Error on final response: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return error_msg
    else:
        final_text = response_message.content or ""
        messages.append({"role": "assistant", "content": final_text})
        return final_text


def handle_slash_command(command: str, messages: list, registry: ToolRegistry = None) -> tuple[bool, str]:
    """
    Handle slash commands. Returns (should_continue: bool, response_text: str)
    """
    cmd_raw = command.strip()
    cmd = cmd_raw.lower().split()[0] if cmd_raw else ""

    if cmd in ("/exit", "/quit", "/q"):
        return False, "Goodbye, sir. Shutting down session."

    elif cmd in ("/clear", "/c"):
        messages.clear()
        messages.append({
            "role": "system",
            "content": (
                "You are JARVIS, Nived's personal AI assistant. "
                "You have access to tools for file operations, running commands, web search, "
                "system status, opening applications/websites, GitHub, and Obsidian note management "
                "(obsidian_create_note, obsidian_daily_note, obsidian_edit_note, obsidian_semantic_search). "
                "Always call the appropriate tool when asked to perform actions or manage Obsidian notes."
            )
        })
        return True, "Conversation history cleared, sir."

    elif cmd in ("/help", "/h"):
        help_text = (
            "JARVIS Core Capabilities & System Access:\n\n"
            "SYSTEM & FILE OPERATIONS:\n"
            "• File Control        - Create, write, read, copy, rename, move, and delete files\n"
            "• Directory Management- Create directories, list contents, and delete folders\n"
            "• Command Execution   - Run shell/PowerShell commands with stdout/stderr capture\n"
            "• System Telemetry     - Monitor real CPU %, RAM %, and Disk utilization\n"
            "• Clipboard Control    - Copy text to system clipboard with fail-proof verification\n"
            "• Desktop & Web        - Launch applications (notepad, calc, chrome, code), websites, and Google search\n"
            "• Full GitHub Suite    - Full account access for repos, issues, PRs, CI status, and notifications\n"
            "• Obsidian Memory      - Local semantic search, note creation, daily notes, and note edits with backups\n\n"
            "SLASH COMMANDS:\n"
            "• /help, /h      - Display this system capability summary\n"
            "• /tools         - List all 25 registered system tools\n"
            "• /status        - Query live CPU, RAM, and Disk vitals\n"
            "• /projects      - View active projects database summary\n"
            "• /reminders     - View pending reminders\n"
            "• /clear, /c     - Reset conversation history\n"
            "• /exit, /quit   - Terminate CLI session"
        )
        return True, help_text

    elif cmd == "/tools":
        if registry:
            tool_list = list(registry.tools.keys())
            return True, f"Registered Tools ({len(tool_list)}):\n• " + "\n• ".join(tool_list)
        return True, "Tools registry initialized."

    elif cmd == "/status":
        from jarvis.tools import get_system_status
        return True, get_system_status()

    elif cmd == "/projects":
        try:
            from jarvis.projects import get_active_projects_summary
            projects = get_active_projects_summary()
            if not projects:
                return True, "No active projects found, sir."
            lines = [f"• {p.get('name')}: {p.get('status', 'active')}" for p in projects]
            return True, "Active Projects:\n" + "\n".join(lines)
        except Exception as e:
            return True, f"Projects status error: {e}"

    elif cmd == "/reminders":
        try:
            from jarvis.memory import Memory
            mem = Memory()
            reminders = mem.get_pending_reminders()
            if not reminders:
                return True, "No pending reminders, sir."
            lines = [f"• [{r.get('due_date', 'no date')}] {r.get('text')}" for r in reminders]
            return True, "Pending Reminders:\n" + "\n".join(lines)
        except Exception as e:
            return True, f"Reminders error: {e}"

    else:
        return True, f"Unknown slash command: '{command}'. Type /help for available commands."


class JARVISCLI:
    """Class wrapper around core chat pipeline for API/Desktop integration."""
    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self.tools = ToolRegistry()
        from jarvis.memory import MemoryManager
        from jarvis.projects import ProjectManager
        self.memory = MemoryManager()
        self.project_manager = ProjectManager()
        self.proactive_monitor = None
        self.voice_manager = None
        
        api_key = os.getenv("NVIDIA_NIM_API_KEY")
        api_config = self.config.get("api", {})
        self.client = OpenAI(
            base_url=api_config.get("base_url", "https://integrate.api.nvidia.com/v1"),
            api_key=api_key
        )
        self.messages = [
            {
                "role": "system",
                "content": (
                    "You are JARVIS, Nived's personal AI assistant. "
                    "You have access to tools for file operations, running commands, web search, "
                    "system status, opening applications/websites, GitHub, and Obsidian note management "
                    "(obsidian_create_note, obsidian_daily_note, obsidian_edit_note, obsidian_semantic_search). "
                    "When requested to create, edit, search, or update Obsidian notes, YOU MUST call the appropriate Obsidian tool."
                )
            }
        ]

    async def process_single_command(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, chat_with_tools, self.client, self.config, self.messages, self.tools
        )

    async def process_command(self, user_message: str) -> str:
        return await self.process_single_command(user_message)

    async def _handle_slash_command(self, command: str) -> str:
        should_continue, response_text = handle_slash_command(command, self.messages, self.tools)
        return response_text


def main():
    print("=" * 50)
    print("         JARVIS - Core Chat Pipeline")
    print("=" * 50)

    config = load_config("config.yaml")
    registry = ToolRegistry()

    api_key = os.getenv("NVIDIA_NIM_API_KEY")
    if not api_key:
        print("[ERROR] NVIDIA_NIM_API_KEY not found in environment or .env file.")
        sys.exit(1)

    api_config = config.get("api", {})
    client = OpenAI(
        base_url=api_config.get("base_url", "https://integrate.api.nvidia.com/v1"),
        api_key=api_key
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are JARVIS, Nived's personal AI assistant. "
                "You have access to tools for file operations, running commands, web search, "
                "system status, opening applications/websites, GitHub, and Obsidian note management "
                "(obsidian_create_note, obsidian_daily_note, obsidian_edit_note, obsidian_semantic_search). "
                "When requested to perform an action (such as creating Obsidian notes, editing notes, "
                "running shell commands, or querying GitHub), call the appropriate tool."
            )
        }
    ]

    print("\nJARVIS initialized and standing by, sir. Type /help for commands or /exit to quit.\n")

    while True:
        try:
            user_input = input("You > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye, sir.")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            should_continue, response_text = handle_slash_command(user_input, messages, registry)
            print(f"\n{response_text}\n")
            if not should_continue:
                break
            continue

        messages.append({"role": "user", "content": user_input})
        response_text = chat_with_tools(client, config, messages, registry)
        print(f"\nJARVIS > {response_text}\n")


if __name__ == "__main__":
    main()
