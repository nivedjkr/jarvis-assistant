"""
Clean, robust Tool Registry and core system tools for JARVIS.
"""

import os
import sys
import shutil
import subprocess
import urllib.parse
import webbrowser
import psutil
import pyperclip
from typing import Dict, List, Any, Callable
from jarvis.github_tool import GitHubTool


def _clean_path(path_str: Any) -> str:
    """Clean and strip whitespace and quotes from file/directory path strings."""
    if not path_str:
        return ""
    s = str(path_str).strip()
    return s.strip("'\"")


def write_file(filepath: str = "", content: Any = "", **kwargs) -> str:
    target_path = _clean_path(filepath or kwargs.get("path") or kwargs.get("file") or kwargs.get("filename"))
    target_content = content if content != "" else kwargs.get("text", "")
    if target_content is None:
        target_content = ""
    if not isinstance(target_content, str):
        target_content = str(target_content)

    if not target_path:
        return "FAILED: No file path provided for write_file."
    try:
        full_path = os.path.abspath(target_path)
        parent_dir = os.path.dirname(full_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(target_content)
        if os.path.exists(full_path):
            size = os.path.getsize(full_path)
            return f"SUCCESS: Created file '{full_path}' ({size} bytes)"
        return f"FAILED: File '{target_path}' was not created."
    except Exception as e:
        return f"FAILED to write file: {str(e)}"


def read_file(filepath: str = "", **kwargs) -> str:
    target_path = _clean_path(filepath or kwargs.get("path") or kwargs.get("file") or kwargs.get("filename"))
    if not target_path:
        return "FAILED: No file path provided for read_file."
    try:
        full_path = os.path.abspath(target_path)
        if not os.path.exists(full_path):
            return f"FAILED: File '{target_path}' not found."
        if os.path.isdir(full_path):
            return f"FAILED: '{target_path}' is a directory, not a file. Use list_files instead."
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        return content if content else f"File '{target_path}' is empty."
    except Exception as e:
        return f"FAILED to read file: {str(e)}"


def list_files(directory: str = ".", **kwargs) -> str:
    target_dir = _clean_path(directory or kwargs.get("path") or kwargs.get("dir") or kwargs.get("folder") or ".")
    if not target_dir:
        target_dir = "."
    try:
        full_path = os.path.abspath(target_dir)
        if not os.path.exists(full_path):
            return f"FAILED: Directory '{target_dir}' not found."
        if not os.path.isdir(full_path):
            return f"FAILED: '{target_dir}' is a file, not a directory."
        entries = os.listdir(full_path)
        if not entries:
            return f"Directory '{full_path}' is empty."
        items = []
        for entry in entries[:50]:
            p = os.path.join(full_path, entry)
            kind = "[DIR]" if os.path.isdir(p) else "[FILE]"
            size = f"({os.path.getsize(p)} bytes)" if os.path.isfile(p) else ""
            items.append(f"{kind} {entry} {size}".strip())
        return f"Contents of {full_path} ({len(entries)} items):\n" + "\n".join(items)
    except Exception as e:
        return f"FAILED to list directory: {str(e)}"


def create_directory(directory: str = "", **kwargs) -> str:
    target_path = _clean_path(directory or kwargs.get("path") or kwargs.get("filepath") or kwargs.get("dir") or kwargs.get("folder") or kwargs.get("name"))
    if not target_path:
        return "FAILED: No directory path provided."
    try:
        full_path = os.path.abspath(target_path)
        os.makedirs(full_path, exist_ok=True)
        if os.path.exists(full_path) and os.path.isdir(full_path):
            return f"SUCCESS: Directory created at '{full_path}'"
        return f"FAILED: Directory '{target_path}' could not be created."
    except Exception as e:
        return f"FAILED to create directory: {str(e)}"


def delete_file(filepath: str = "", **kwargs) -> str:
    target_path = _clean_path(filepath or kwargs.get("path") or kwargs.get("file"))
    if not target_path:
        return "FAILED: No file path provided for delete_file."
    try:
        full_path = os.path.abspath(target_path)
        if not os.path.exists(full_path):
            return f"FAILED: Path '{target_path}' does not exist."
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
            return f"SUCCESS: Deleted directory '{full_path}'"
        os.remove(full_path)
        if not os.path.exists(full_path):
            return f"SUCCESS: Deleted file '{full_path}'"
        return f"FAILED: File '{target_path}' still exists after delete attempt."
    except Exception as e:
        return f"FAILED to delete file: {str(e)}"


def copy_file(source: str = "", destination: str = "", **kwargs) -> str:
    src_path = _clean_path(source or kwargs.get("src") or kwargs.get("from_path"))
    dst_path = _clean_path(destination or kwargs.get("dst") or kwargs.get("to_path"))
    if not src_path or not dst_path:
        return "FAILED: Both source and destination paths are required for copy_file."
    try:
        src_full = os.path.abspath(src_path)
        dst_full = os.path.abspath(dst_path)
        if not os.path.exists(src_full):
            return f"FAILED: Source path '{src_path}' does not exist."
        if os.path.isdir(src_full):
            shutil.copytree(src_full, dst_full, dirs_exist_ok=True)
        else:
            os.makedirs(os.path.dirname(dst_full) or '.', exist_ok=True)
            shutil.copy2(src_full, dst_full)
        if os.path.exists(dst_full):
            return f"SUCCESS: Copied '{src_full}' to '{dst_full}'"
        return f"FAILED: Copy operation failed."
    except Exception as e:
        return f"FAILED to copy file: {str(e)}"


def rename_file(source: str = "", destination: str = "", **kwargs) -> str:
    src_path = _clean_path(source or kwargs.get("src") or kwargs.get("old_path") or kwargs.get("filepath"))
    dst_path = _clean_path(destination or kwargs.get("dst") or kwargs.get("new_path") or kwargs.get("target"))
    if not src_path or not dst_path:
        return "FAILED: Both source and destination paths are required for rename_file."
    try:
        src_full = os.path.abspath(src_path)
        dst_full = os.path.abspath(dst_path)
        if not os.path.exists(src_full):
            return f"FAILED: Source path '{src_path}' does not exist."
        os.makedirs(os.path.dirname(dst_full) or '.', exist_ok=True)
        shutil.move(src_full, dst_full)
        if os.path.exists(dst_full):
            return f"SUCCESS: Renamed/Moved '{src_full}' to '{dst_full}'"
        return "FAILED: Rename/move operation failed."
    except Exception as e:
        return f"FAILED to rename file: {str(e)}"


def open_application(app_name: str = "", **kwargs) -> str:
    target_name = (app_name or kwargs.get("name") or kwargs.get("application") or "").strip()
    if not target_name:
        return "FAILED: No application name provided."
    
    try:
        if os.name == 'nt':
            try:
                os.startfile(target_name)
                return f"Opened application '{target_name}', sir."
            except Exception:
                pass
        
        app_lower = target_name.lower()
        cmd = target_name
        if app_lower == 'notepad':
            cmd = 'notepad.exe'
        elif app_lower in ('calc', 'calculator'):
            cmd = 'calc.exe'
        elif app_lower in ('code', 'vscode'):
            cmd = 'code'
        elif app_lower == 'chrome':
            cmd = 'chrome.exe'
            
        subprocess.Popen(cmd, shell=True)
        return f"Opened application '{target_name}', sir."
    except Exception as e:
        return f"FAILED to open '{target_name}': {str(e)}"


def open_website(url: str = "", **kwargs) -> str:
    target_url = (url or kwargs.get("link") or kwargs.get("website") or "").strip()
    if not target_url:
        return "FAILED: No URL provided."
    if not (target_url.startswith("http://") or target_url.startswith("https://")):
        target_url = "https://" + target_url
    try:
        if os.name == 'nt':
            subprocess.Popen(f'start "" "{target_url}"', shell=True)
        else:
            webbrowser.open(target_url)
        return f"Opened website '{target_url}', sir."
    except Exception as e:
        return f"FAILED to open website: {str(e)}"


def web_search(query: str = "", **kwargs) -> str:
    target_query = (query or kwargs.get("search") or kwargs.get("q") or "").strip()
    if not target_query:
        return "FAILED: No search query provided."
    try:
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(target_query)}"
        if os.name == 'nt':
            subprocess.Popen(f'start "" "{search_url}"', shell=True)
        else:
            webbrowser.open(search_url)
        return f"Opened Google search for '{target_query}', sir."
    except Exception as e:
        return f"FAILED to perform search: {str(e)}"


def run_command(command: str = "", **kwargs) -> str:
    target_cmd = command or kwargs.get("cmd") or ""
    if not target_cmd:
        return "FAILED: No command provided."
    try:
        result = subprocess.run(
            target_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        output = []
        if stdout:
            output.append(f"STDOUT:\n{stdout}")
        if stderr:
            output.append(f"STDERR:\n{stderr}")
        if not output:
            output.append("Command executed with no output.")
        return "\n".join(output)
    except subprocess.TimeoutExpired:
        return "FAILED: Command timed out after 30 seconds."
    except Exception as e:
        return f"FAILED to execute command: {str(e)}"


def copy_to_clipboard(text: Any = "", **kwargs) -> str:
    target_text = text if text != "" else kwargs.get("content") or kwargs.get("string") or kwargs.get("value") or ""
    if target_text is None:
        target_text = ""
    if not isinstance(target_text, str):
        target_text = str(target_text)

    if not target_text:
        return "FAILED: No text provided to copy to clipboard."

    copied_ok = False
    try:
        pyperclip.copy(target_text)
        copied_ok = True
        try:
            pasted = pyperclip.paste()
            if pasted == target_text:
                return f"Copied to clipboard: '{target_text[:50]}...'" if len(target_text) > 50 else f"Copied to clipboard: '{target_text}'"
        except Exception:
            pass
    except Exception:
        copied_ok = False

    # Windows fallback via clip.exe if pyperclip encountered issues
    if os.name == 'nt':
        try:
            proc = subprocess.Popen('clip', stdin=subprocess.PIPE, shell=True)
            proc.communicate(target_text.encode('utf-8'))
            if proc.returncode == 0 or proc.returncode is None:
                return f"Copied to clipboard: '{target_text[:50]}...'" if len(target_text) > 50 else f"Copied to clipboard: '{target_text}'"
        except Exception as e:
            if not copied_ok:
                return f"FAILED to copy to clipboard: {str(e)}"

    if copied_ok:
        return f"Copied to clipboard: '{target_text[:50]}...'" if len(target_text) > 50 else f"Copied to clipboard: '{target_text}'"

    return "FAILED: Could not copy to clipboard."


def get_system_status(**kwargs) -> str:
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        return (
            f"System Status:\n"
            f"- CPU Usage: {cpu}%\n"
            f"- RAM Usage: {mem.percent}% ({mem.used // (1024**2)}MB / {mem.total // (1024**2)}MB)\n"
            f"- Disk Usage: {disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)"
        )
    except Exception as e:
        return f"FAILED to get system status: {str(e)}"


TOOLS_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write text content to a file. Verifies creation on disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Target file path"},
                    "content": {"type": "string", "description": "Text content to write"}
                },
                "required": ["filepath", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read and return the contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Path of the file to read"}
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and subdirectories in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory path (default is '.')"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a new directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Path of the directory to create"}
                },
                "required": ["directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file or directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Path of the file or directory to delete"}
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "Copy a file or directory to a new destination.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source path"},
                    "destination": {"type": "string", "description": "Destination path"}
                },
                "required": ["source", "destination"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rename_file",
            "description": "Rename or move a file or directory to a new path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Current file/directory path"},
                    "destination": {"type": "string", "description": "New file/directory path"}
                },
                "required": ["source", "destination"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "Open a desktop application by name (e.g. notepad, calc, chrome, code).",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name of the application to open"}
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_website",
            "description": "Open a website URL in the default browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Website URL to open"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Open a Google search query in the browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command and return its output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command string to run"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "copy_to_clipboard",
            "description": "Copy text to the system clipboard and verify.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to copy to clipboard"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "Get current CPU, RAM, and disk utilization.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_issues",
            "description": "List GitHub issues via gh CLI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name (owner/repo)"},
                    "state": {"type": "string", "description": "Issue state ('open', 'closed', 'all')"},
                    "limit": {"type": "integer", "description": "Max number of issues"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_prs",
            "description": "List GitHub pull requests via gh CLI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name (owner/repo)"},
                    "state": {"type": "string", "description": "PR state ('open', 'closed', 'merged', 'all')"},
                    "limit": {"type": "integer", "description": "Max number of PRs"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ci_status",
            "description": "Get latest GitHub Actions CI run status via gh CLI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name (owner/repo)"},
                    "limit": {"type": "integer", "description": "Max number of runs"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "repo_info",
            "description": "Get repository summary details via gh CLI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string", "description": "Repository name (owner/repo)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_repos",
            "description": "List user's GitHub repositories via gh CLI.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max number of repositories"}
                }
            }
        }
    }
]


class ToolRegistry:
    """Registry managing tool schemas, implementations, and execution."""
    
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.schemas: List[Dict[str, Any]] = []
        self.last_transactions: List[Dict[str, Any]] = []
        self._gh_tool = GitHubTool()
        
        self._register_default_tools()
        tool_names = list(self.tools.keys())
        print(f"[TOOLS] Registered {len(tool_names)} tools: [{', '.join(tool_names)}]")

    def register(self, name: str, func: Callable, schema: Dict[str, Any]):
        self.tools[name] = func
        self.schemas.append(schema)

    def _register_default_tools(self):
        schema_map = {s["function"]["name"]: s for s in TOOLS_SCHEMAS}
        
        core_tools = [
            ("write_file", write_file),
            ("read_file", read_file),
            ("list_files", list_files),
            ("create_directory", create_directory),
            ("delete_file", delete_file),
            ("copy_file", copy_file),
            ("rename_file", rename_file),
            ("open_application", open_application),
            ("open_website", open_website),
            ("web_search", web_search),
            ("run_command", run_command),
            ("copy_to_clipboard", copy_to_clipboard),
            ("get_system_status", get_system_status),
        ]
        for name, func in core_tools:
            if name in schema_map:
                self.register(name, func, schema_map[name])

        gh = self._gh_tool
        gh_tools = [
            ("list_issues", lambda **kw: gh.list_issues(repo=kw.get('repo'), state=kw.get('state', 'open'), limit=kw.get('limit', 10))),
            ("list_prs", lambda **kw: gh.list_prs(repo=kw.get('repo'), state=kw.get('state', 'open'), limit=kw.get('limit', 10))),
            ("ci_status", lambda **kw: gh.ci_status(repo=kw.get('repo'), limit=kw.get('limit', 5))),
            ("repo_info", lambda **kw: gh.repo_info(repo=kw.get('repo'))),
            ("list_repos", lambda **kw: gh.list_repos(limit=kw.get('limit') or 50)),
        ]
        for name, func in gh_tools:
            if name in schema_map:
                self.register(name, func, schema_map[name])

    def execute_tool(self, name: str, kwargs: dict = None) -> str:
        if kwargs is None:
            kwargs = {}
        print(f"[TOOL] Executing {name} with args: {kwargs}")
        if name not in self.tools:
            res = f"FAILED: Tool '{name}' is not registered."
            print(f"[TOOL] Result: {res}")
            self.last_transactions.append({"tool": name, "args": kwargs, "result": res})
            return res
        try:
            res = self.tools[name](**kwargs)
            print(f"[TOOL] Result: {res}")
            self.last_transactions.append({"tool": name, "args": kwargs, "result": res})
            return str(res)
        except Exception as e:
            res = f"FAILED: Error executing tool '{name}': {str(e)}"
            print(f"[TOOL] Result: {res}")
            self.last_transactions.append({"tool": name, "args": kwargs, "result": res})
            return res
