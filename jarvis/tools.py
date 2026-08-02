"""
Tools for JARVIS
Provides file operations, shell commands, and other utilities
"""

import os
import subprocess
import shutil
import webbrowser
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from jarvis.apps import AppRegistry


console = Console()


class Tool:
    """Base class for all tools"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    async def execute(self, **kwargs) -> str:
        """Execute the tool"""
        raise NotImplementedError


class FileReadTool(Tool):
    """Tool to read file contents"""
    
    def __init__(self):
        super().__init__("read_file", "Read the contents of a file")
    
    async def execute(self, filepath: str) -> str:
        """Read file contents"""
        try:
            path = Path(filepath)
            if not path.exists():
                return f"Error: File '{filepath}' not found"
            
            if not path.is_file():
                return f"Error: '{filepath}' is not a file"
            
            resolved_path = path.resolve()
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            console.print(f"[dim cyan][RAW DISK READ] Path: '{resolved_path}' | Bytes: {len(content)}[/dim cyan]", highlight=False)
            return f"Contents of file '{filepath}' (resolved path: {resolved_path}):\n{content}"
        except Exception as e:
            return f"Error reading file: {str(e)}"


class FileWriteTool(Tool):
    """Tool to write content to a file"""
    
    def __init__(self, confirm_dangerous: bool = True):
        super().__init__("write_file", "Write content to a file")
        self.confirm_dangerous = confirm_dangerous
    
    async def execute(self, filepath: str, content: str, confirm: bool = True) -> str:
        """Write content to file"""
        try:
            path = Path(filepath)
            resolved_path = path.resolve()
            
            # Check if file exists and ask for confirmation
            if path.exists() and confirm and self.confirm_dangerous:
                if not Confirm.ask(f"[yellow]File '{filepath}' already exists. Overwrite?"):
                    return "Operation cancelled by user"
            
            # Create parent directories if they don't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return f"Successfully wrote to file '{filepath}' at resolved path: {resolved_path} (Written content: '{content}')"
        except Exception as e:
            return f"Error writing file: {str(e)}"


class FileListTool(Tool):
    """Tool to list files in a directory"""
    
    def __init__(self):
        super().__init__("list_files", "List files in a directory")
    
    async def execute(self, directory: str = ".", recursive: bool = False) -> str:
        """List files in directory"""
        try:
            path = Path(directory)
            if not path.exists():
                return f"Error: Directory '{directory}' not found"
            
            if not path.is_dir():
                return f"Error: '{directory}' is not a directory"
            
            if recursive:
                files = []
                for item in path.rglob("*"):
                    files.append(f"{'[DIR]' if item.is_dir() else '[FILE]'} {item}")
                return "\n".join(files)
            else:
                items = []
                for item in path.iterdir():
                    items.append(f"{'[DIR]' if item.is_dir() else '[FILE]'} {item.name}")
                return "\n".join(items) if items else "Directory is empty"
        except Exception as e:
            return f"Error listing files: {str(e)}"


class FileSearchTool(Tool):
    """Tool to search for files"""
    
    def __init__(self):
        super().__init__("search_files", "Search for files by pattern")
    
    async def execute(self, pattern: str, directory: str = ".") -> str:
        """Search for files matching pattern"""
        try:
            path = Path(directory)
            if not path.exists():
                return f"Error: Directory '{directory}' not found"
            
            matches = list(path.rglob(pattern))
            if not matches:
                return f"No files found matching '{pattern}'"
            
            return "\n".join(str(m) for m in matches)
        except Exception as e:
            return f"Error searching files: {str(e)}"


class ShellCommandTool(Tool):
    """Tool to execute shell commands"""
    
    def __init__(self, confirm_dangerous: bool = True, logger=None):
        super().__init__("shell_command", "Execute a shell command")
        self.confirm_dangerous = confirm_dangerous
        self.logger = logger
    
    def _is_dangerous(self, command: str) -> bool:
        """Check if command is potentially dangerous"""
        dangerous_keywords = [
            "rm", "del", "format", "shutdown", "reboot",
            "dd", "mkfs", "fdisk", ">", ">>"
        ]
        return any(keyword in command.lower() for keyword in dangerous_keywords)
    
    async def execute(self, command: str, confirm: bool = True) -> str:
        """Execute shell command"""
        # Check if command is dangerous
        if self._is_dangerous(command) and confirm and self.confirm_dangerous:
            console.print(Panel(
                f"[red]⚠️  Potentially dangerous command:[/red]\n{command}",
                title="Warning"
            ))
            if not Confirm.ask("[yellow]Do you want to execute this command?"):
                return "Operation cancelled by user"
        
        try:
            # Log the command
            if self.logger:
                self.logger.log(command, approved=True)
            
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\n[stderr]: {result.stderr}"
            
            if result.returncode != 0:
                output += f"\n[Exit code: {result.returncode}]"
            
            # Log result
            if self.logger:
                self.logger.log(command, approved=True, result=str(result.returncode))
            
            return f"Executed shell command '{command}' (Exit code: {result.returncode}):\n{output}" if output else f"Executed shell command '{command}' (Exit code: {result.returncode}, no output)"
            
        except subprocess.TimeoutExpired:
            return f"Error: Command '{command}' timed out"
        except Exception as e:
            if self.logger:
                self.logger.log(command, approved=False, result=str(e))
            return f"Error executing command: {str(e)}"


class DirectoryTool(Tool):
    """Tool to create/delete directories"""
    
    def __init__(self, confirm_dangerous: bool = True):
        super().__init__("directory", "Create or delete directories")
        self.confirm_dangerous = confirm_dangerous
    
    async def execute(self, action: str, path: str, confirm: bool = True) -> str:
        """Create or delete directory"""
        try:
            dir_path = Path(path)
            resolved_path = dir_path.resolve()
            
            if action == "create":
                dir_path.mkdir(parents=True, exist_ok=True)
                return f"Created directory '{path}' successfully at resolved path: {resolved_path}"
            
            elif action == "delete":
                if confirm and self.confirm_dangerous:
                    if not Confirm.ask(f"[yellow]Delete directory '{path}' and all its contents?"):
                        return "Operation cancelled by user"
                
                shutil.rmtree(dir_path)
                return f"Deleted directory '{path}' at resolved path: {resolved_path}"
            
            else:
                return f"Unknown action: {action}. Use 'create' or 'delete'"
                
        except Exception as e:
            return f"Error with directory operation: {str(e)}"


class PDFSummarizeTool(Tool):
    """Tool to extract text from a PDF file for summarization"""

    def __init__(self, api_client=None):
        super().__init__("summarize_pdf", "Extract text from a PDF file and summarize paper findings")
        self.api_client = api_client

    async def execute(self, filepath: str) -> str:
        """Extract text from PDF and return raw extracted text with paper structure summary"""
        try:
            path = Path(filepath)
            if not path.exists():
                return f"Error: PDF file '{filepath}' not found"
            if not path.is_file():
                return f"Error: '{filepath}' is not a file"

            resolved_path = path.resolve()
            import pypdf
            reader = pypdf.PdfReader(str(resolved_path))
            pages_text = []
            for idx, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages_text.append(text)

            full_text = "\n".join(pages_text).strip()
            if not full_text:
                return f"Error: Could not extract text from PDF '{filepath}' (file may be scanned image or empty)."

            console.print(f"[dim cyan][PDF EXTRACTED TEXT] Path: '{resolved_path}' | Pages: {len(reader.pages)} | Characters: {len(full_text)}[/dim cyan]", highlight=False)
            
            return f"Raw Extracted PDF Content from '{filepath}' ({len(reader.pages)} pages):\n\n{full_text[:3000]}"
        except Exception as e:
            return f"Error extracting text from PDF '{filepath}': {str(e)}"


class GitStatusTool(Tool):
    """Tool to execute git status, git branch, and git log -1"""

    def __init__(self):
        super().__init__("git_status", "Get real git status, current branch, and recent commit log")

    async def execute(self, directory: str = ".") -> str:
        """Execute real git status commands via subprocess"""
        try:
            cwd = str(Path(directory).resolve())
            status_res = subprocess.run("git status", shell=True, capture_output=True, text=True, cwd=cwd)
            branch_res = subprocess.run("git branch --show-current", shell=True, capture_output=True, text=True, cwd=cwd)
            log_res = subprocess.run("git log -1 --oneline", shell=True, capture_output=True, text=True, cwd=cwd)

            output = f"Git Status in '{cwd}':\n"
            output += f"Branch: {branch_res.stdout.strip() if branch_res.stdout else 'Unknown'}\n"
            output += f"Recent Commit: {log_res.stdout.strip() if log_res.stdout else 'None'}\n\n"
            output += f"Status Output:\n{status_res.stdout if status_res.stdout else status_res.stderr}"
            return output
        except Exception as e:
            return f"Error running git commands: {str(e)}"


class AppLaunchTool(Tool):
    """Tool to launch software applications"""
    
    def __init__(self, app_registry: Optional[AppRegistry] = None):
        super().__init__("open_application", "Launch an installed software application or Windows tool")
        self.app_registry = app_registry or AppRegistry()
        
    async def execute(self, app_name: str = "", name: str = "") -> str:
        """Launch application by name"""
        target = app_name or name
        try:
            cmd, matches, matched_key = self.app_registry.resolve_app(target)
            
            if cmd:
                if cmd.startswith("start "):
                    os.system(cmd)
                else:
                    subprocess.Popen(cmd, shell=True)
                msg = f"Launched application: '{matched_key or target}' ({cmd})"
                if matched_key:
                    msg = f"⚠️ [CONFIDENCE WARNING] I matched '{target}' to '{matched_key}' — confirm this is correct?\n" + msg
                return msg
            
            if matches:
                matches_str = ", ".join(f"'{m}'" for m in matches)
                return f"Multiple matching applications found for '{target}': {matches_str}. Please specify which one."
            
            # Fallback to os.startfile on Windows
            if hasattr(os, "startfile"):
                try:
                    os.startfile(target)
                    return f"Opened '{target}' via Windows launcher."
                except Exception:
                    pass
            
            return f"Error: Application '{target}' not recognized. Use '/addapp {target} <path_or_cmd>' to register it."
        except Exception as e:
            return f"Error launching application '{target}': {str(e)}"


class URLOpenTool(Tool):
    """Tool to open URLs or perform web searches"""
    
    def __init__(self):
        super().__init__("open_url", "Open a URL or search query in default web browser")
        
    async def execute(self, url_or_query: str) -> str:
        """Open URL or search query"""
        try:
            target = url_or_query.strip()
            if not target:
                return "Error: No URL or search query provided"
            
            if target.startswith(("http://", "https://", "www.")) or ("." in target and " " not in target):
                url = target if target.startswith(("http://", "https://")) else f"https://{target}"
                webbrowser.open(url)
                return f"Opened URL in browser: {url}"
            else:
                query_encoded = urllib.parse.quote(target)
                search_url = f"https://www.google.com/search?q={query_encoded}"
                webbrowser.open(search_url)
                return f"Opened Google search for: '{target}'"
        except Exception as e:
            return f"Error opening URL/browser: {str(e)}"


class WebsiteOpenTool(Tool):
    """Tool to open common websites by alias"""
    
    SITE_ALIASES = {
        "youtube": "https://www.youtube.com",
        "gmail": "https://mail.google.com",
        "github": "https://github.com",
        "google": "https://www.google.com",
        "reddit": "https://www.reddit.com",
        "twitter": "https://x.com",
        "x": "https://x.com",
        "stackoverflow": "https://stackoverflow.com",
        "stack overflow": "https://stackoverflow.com",
        "linkedin": "https://www.linkedin.com",
        "wikipedia": "https://www.wikipedia.org"
    }
    
    def __init__(self):
        super().__init__("open_website", "Open a common website in the browser by name (youtube, github, gmail, etc.)")
        
    async def execute(self, site_name: str) -> str:
        """Open common website by alias"""
        try:
            name_clean = site_name.strip().lower()
            url = self.SITE_ALIASES.get(name_clean)
            
            if not url:
                for alias, site_url in self.SITE_ALIASES.items():
                    if name_clean in alias or alias in name_clean:
                        url = site_url
                        break
            
            if url:
                webbrowser.open(url)
                return f"Opened website: '{site_name}' ({url})"
            else:
                search_url = f"https://www.google.com/search?q={urllib.parse.quote(site_name)}"
                webbrowser.open(search_url)
                return f"Opened Google search for website: '{site_name}'"
        except Exception as e:
            return f"Error opening website '{site_name}': {str(e)}"


class ToolRegistry:
    """Registry for all available tools"""
    
    def __init__(self, confirm_dangerous: bool = True, logger=None, app_registry: Optional[AppRegistry] = None):
        self.tools: Dict[str, Tool] = {}
        self.confirm_dangerous = confirm_dangerous
        self.logger = logger
        self.app_registry = app_registry or AppRegistry()
        self.last_transactions: List[Dict[str, Any]] = []
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register default tools"""
        self.register(FileReadTool())
        self.register(FileWriteTool(self.confirm_dangerous))
        self.register(FileListTool())
        self.register(FileSearchTool())
        self.register(ShellCommandTool(self.confirm_dangerous, self.logger))
        self.register(DirectoryTool(self.confirm_dangerous))
        self.register(AppLaunchTool(self.app_registry))
        self.register(URLOpenTool())
        self.register(WebsiteOpenTool())
        self.register(PDFSummarizeTool())
        self.register(GitStatusTool())
    
    def register(self, tool: Tool):
        """Register a new tool"""
        self.tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name"""
        return self.tools.get(name)
    
    def list_tools(self) -> List[Dict[str, str]]:
        """List all available tools"""
        return [
            {"name": name, "description": tool.description}
            for name, tool in self.tools.items()
        ]
    
    async def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Execute a tool by name"""
        tool = self.get_tool(tool_name)
        if not tool:
            return f"Error: Tool '{tool_name}' not found"
        
        from jarvis.ui import ui, UIState
        ui.set_state(UIState.EXECUTING)
        args_str = ", ".join(f"{k}='{v}'" if isinstance(v, str) else f"{k}={v}" for k, v in kwargs.items())
        exec_desc = f"{tool_name} {args_str}".strip()
        ui.render_tool_exec(exec_desc)
        
        result = await tool.execute(**kwargs)
        ui.set_state(UIState.IDLE)
        
        from datetime import datetime
        tx = {
            "tool": tool_name,
            "kwargs": kwargs,
            "result": str(result),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        self.last_transactions.insert(0, tx)
        if len(self.last_transactions) > 5:
            self.last_transactions.pop()
            
        return result
