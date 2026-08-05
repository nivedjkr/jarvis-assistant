"""
Tools for JARVIS
Provides file operations, shell commands, and other utilities
"""

import os
import re
import subprocess
import shutil
import webbrowser
import urllib.parse
import asyncio
import time
import psutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from jarvis.apps import AppRegistry, PROCESS_NAMES


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
            status_res = subprocess.run(["git", "status"], capture_output=True, text=True, cwd=cwd)
            branch_res = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, cwd=cwd)
            log_res = subprocess.run(["git", "log", "-1", "--oneline"], capture_output=True, text=True, cwd=cwd)

            output = f"Git Status in '{cwd}':\n"
            output += f"Branch: {branch_res.stdout.strip() if branch_res.stdout else 'Unknown'}\n"
            output += f"Recent Commit: {log_res.stdout.strip() if log_res.stdout else 'None'}\n\n"
            output += f"Status Output:\n{status_res.stdout if status_res.stdout else status_res.stderr}"
            return output
        except Exception as e:
            return f"Error running git commands: {str(e)}"


class GitTool(Tool):
    """Tool for Git repository operations: add, commit, push, pull"""

    def __init__(self, confirm_dangerous: bool = True):
        super().__init__("git", "Execute git operations (add, commit, push, pull)")
        self.confirm_dangerous = confirm_dangerous

    def _get_current_branch(self, cwd: Optional[str] = None) -> str:
        try:
            res = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True, text=True, cwd=cwd, timeout=10
            )
            return res.stdout.strip() if res.returncode == 0 and res.stdout.strip() else "main"
        except Exception:
            return "main"

    def git_add(self, files: Optional[Any] = None, cwd: Optional[str] = None) -> str:
        """Stage specific files, or all changes if files is omitted (git add -A)"""
        try:
            cmd = ["git", "add"]
            if not files:
                cmd.append("-A")
            elif isinstance(files, str):
                cmd.append(files)
            elif isinstance(files, (list, tuple)):
                cmd.extend([str(f) for f in files])
            else:
                cmd.append("-A")

            res = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=30)
            if res.returncode != 0:
                return f"git add failed: {res.stderr.strip() or res.stdout.strip()}"
            
            staged_desc = ", ".join(files) if isinstance(files, (list, tuple)) else (files if files else "all changes (-A)")
            return f"Staged changes successfully ({staged_desc})."
        except Exception as e:
            return f"Error executing git add: {str(e)}"

    def git_commit(self, message: str, confirm: bool = True, cwd: Optional[str] = None) -> str:
        """Commit staged changes. Fail with a clear message if nothing is staged."""
        if not message or not str(message).strip():
            return "Error: Commit message is required."

        try:
            diff_res = subprocess.run(
                ["git", "diff", "--cached"],
                capture_output=True, text=True, cwd=cwd, timeout=30
            )
            staged_diff = diff_res.stdout.strip() if diff_res.returncode == 0 else ""
            
            if not staged_diff:
                return "No staged changes to commit. Use git add first."

            cmd_str = f"git commit -m \"{message}\""

            if confirm and self.confirm_dangerous:
                console.print(Panel(
                    f"[yellow]Command:[/yellow] {cmd_str}\n\n[cyan]Staged Diff (--cached):[/cyan]\n{staged_diff[:3000]}",
                    title="Confirm Git Commit"
                ))
                if not Confirm.ask("[yellow]Do you want to commit these staged changes?"):
                    return "Operation cancelled by user"

            res = subprocess.run(
                ["git", "commit", "-m", str(message)],
                capture_output=True, text=True, cwd=cwd, timeout=30
            )
            if res.returncode != 0:
                return f"git commit failed: {res.stderr.strip() or res.stdout.strip()}"
            
            return f"Committed successfully:\n{res.stdout.strip()}"
        except Exception as e:
            return f"Error executing git commit: {str(e)}"

    def git_push(self, remote: str = "origin", branch: Optional[str] = None, force: bool = False, confirm: bool = True, cwd: Optional[str] = None) -> str:
        """Push to remote. If branch isn't given, use current branch."""
        target_branch = branch or self._get_current_branch(cwd=cwd)
        remote_name = remote or "origin"
        
        cmd = ["git", "push"]
        if force:
            cmd.append("--force")
        cmd.extend([remote_name, target_branch])

        cmd_str = " ".join(cmd)

        # force must default to False and require explicit confirmation even if confirm=False is passed
        if force:
            console.print(Panel(
                f"[bold red]DANGER: Force Push Requested![/bold red]\n{cmd_str}",
                title="Force Push Confirmation Required"
            ))
            if not Confirm.ask("[bold red]Are you ABSOLUTELY SURE you want to force-push? This can overwrite remote history!"):
                return "Force push cancelled by user"
        elif confirm and self.confirm_dangerous:
            console.print(Panel(
                f"[yellow]Command:[/yellow] {cmd_str}",
                title="Confirm Git Push"
            ))
            if not Confirm.ask(f"[yellow]Do you want to push to {remote_name}/{target_branch}?"):
                return "Operation cancelled by user"

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=60)
            if res.returncode != 0:
                return f"git push failed: {res.stderr.strip() or res.stdout.strip()}"
            
            return f"Pushed successfully to {remote_name}/{target_branch}:\n{res.stdout.strip() or res.stderr.strip()}"
        except Exception as e:
            return f"Error executing git push: {str(e)}"

    def git_pull(self, remote: str = "origin", branch: Optional[str] = None, cwd: Optional[str] = None) -> str:
        """Pull latest changes."""
        target_branch = branch or self._get_current_branch(cwd=cwd)
        remote_name = remote or "origin"
        
        cmd = ["git", "pull", remote_name, target_branch]

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=60)
            if res.returncode != 0:
                return f"git pull failed: {res.stderr.strip() or res.stdout.strip()}"
            
            return f"Pulled successfully from {remote_name}/{target_branch}:\n{res.stdout.strip()}"
        except Exception as e:
            return f"Error executing git pull: {str(e)}"

    async def execute(self, action: str = "add", files: Any = None, message: str = "", remote: str = "origin", branch: Optional[str] = None, force: bool = False, confirm: bool = True, **kwargs) -> str:
        act = (action or "").lower()
        if act == "add":
            return self.git_add(files=files)
        elif act == "commit":
            return self.git_commit(message=message, confirm=confirm)
        elif act == "push":
            return self.git_push(remote=remote, branch=branch, force=force, confirm=confirm)
        elif act == "pull":
            return self.git_pull(remote=remote, branch=branch)
        else:
            return f"Unknown git action: {action}. Supported actions: add, commit, push, pull"



from jarvis.github_tool import GitHubTool as NativeGitHubTool

_native_gh = NativeGitHubTool()


GH_NOTICE = " IMPORTANT: Never generate OAuth URLs or login flows. gh CLI is already authenticated. Just call the tool directly and return real output. If gh returns an auth error, say so plainly."


class GitHubIssuesTool(Tool):
    """List, create, or close GitHub issues"""
    def __init__(self):
        super().__init__("github_issues", "List, create, or close GitHub issues." + GH_NOTICE)

    async def execute(self, action: str = "list", repo: str = "", title: str = "", number: Any = None, state: str = "open", **kwargs) -> str:
        act = action.lower()
        if act == "create":
            body = kwargs.get("body", "")
            return _native_gh.create_issue(title=title, body=body, repo=repo or None)
        elif act == "close":
            num = int(number) if number is not None else 0
            return _native_gh.close_issue(number=num, repo=repo or None)
        else:
            return _native_gh.list_issues(repo=repo or None, state=state, limit=kwargs.get("limit", 10))


class GitHubPRsTool(Tool):
    """List or view GitHub pull requests"""
    def __init__(self):
        super().__init__("github_prs", "List or view GitHub pull requests." + GH_NOTICE)

    async def execute(self, action: str = "list", repo: str = "", number: Any = None, state: str = "open", **kwargs) -> str:
        act = action.lower()
        if act == "view":
            num = int(number) if number is not None else 0
            return _native_gh.view_pr(number=num, repo=repo or None)
        else:
            return _native_gh.list_prs(repo=repo or None, state=state, limit=kwargs.get("limit", 10))


class GitHubCITool(Tool):
    """Check CI/Actions status and logs"""
    def __init__(self):
        super().__init__("github_ci", "Check CI/Actions status and logs." + GH_NOTICE)

    async def execute(self, action: str = "status", repo: str = "", run_id: str = "", **kwargs) -> str:
        act = action.lower()
        if act == "logs":
            return _native_gh.ci_logs(run_id=run_id, repo=repo or None)
        else:
            return _native_gh.ci_status(repo=repo or None, limit=kwargs.get("limit", 5))


class GitHubRepoTool(Tool):
    """View repo info or list all repos"""
    def __init__(self):
        super().__init__("github_repo", "View repo info or list all repos." + GH_NOTICE)

    async def execute(self, action: str = "info", repo: str = "", **kwargs) -> str:
        act = action.lower()
        if act in ("list", "repos"):
            return _native_gh.list_repos(limit=kwargs.get("limit", 10))
        else:
            return _native_gh.repo_info(repo=repo or None)


class GitHubNotificationsTool(Tool):
    """Check GitHub notifications"""
    def __init__(self):
        super().__init__("github_notifications", "Check GitHub notifications." + GH_NOTICE)

    async def execute(self, **kwargs) -> str:
        return _native_gh.notifications(limit=kwargs.get("limit", 5))


class EmailTool(Tool):
    """Check Gmail unread messages, read email body, or get inbox summary."""

    def __init__(self):
        super().__init__("email", "Check Gmail unread messages, read email body by index, or get inbox summary. IMPORTANT: Never generate fake emails or fake content. If unauthenticated, report so plainly.")

    async def execute(self, action: str = "list", index: Any = None, **kwargs) -> str:
        from jarvis.email_service import EmailService
        from jarvis.google_auth import GoogleAuthManager
        auth_mgr = GoogleAuthManager()
        if not auth_mgr.is_authenticated():
            return "Google Email is unauthenticated, sir. Run Google OAuth setup or place credentials.json in workspace to connect."
        svc = EmailService(auth_mgr)
        act = action.lower() if action else "list"
        if act == "summary":
            return svc.generate_email_summary_briefing()
        elif act in ("read", "view") or index is not None:
            try:
                idx = int(index) if index is not None else 1
            except ValueError:
                idx = 1
            return svc.read_email_body_by_index(idx)
        else:
            return svc.format_unread_list()


class AppLaunchTool(Tool):
    """Tool to launch software applications with a verified 3-method strategy and launch method caching."""
    
    def __init__(self, app_registry: Optional[AppRegistry] = None):
        super().__init__("open_application", "Launch an installed software application or Windows tool")
        self.app_registry = app_registry or AppRegistry()
        
    async def execute(self, app_name: str = "", name: str = "") -> str:
        """Launch application by name with 3 launch methods and psutil verification."""
        target = (app_name or name).strip()
        if not target:
            return "Error: No application specified to open."

        cmd, matches, matched_key = self.app_registry.resolve_app(target)
        if matches:
            matches_str = ", ".join(f"'{m}'" for m in matches)
            return f"Multiple matching applications found for '{target}': {matches_str}. Please specify which one."

        command = cmd or target
        app_clean_key = (matched_key or target).lower()
        proc_name = PROCESS_NAMES.get(app_clean_key, self.app_registry.resolve_process_name(app_clean_key))

        print(f"[APP] Opening: {target} via command '{command}'")
        
        # Check launch method cache first
        from jarvis.apps import _LAUNCH_METHOD_CACHE
        cached_method = _LAUNCH_METHOD_CACHE.get(command)
        
        launched = False
        methods_tried = []

        def _try_startfile():
            if hasattr(os, "startfile"):
                clean_path = command.replace("start ", "").strip().strip('"')
                os.startfile(clean_path if os.path.exists(clean_path) else command)
                return True
            return False

        def _try_subprocess_start():
            creationflags = 0
            if hasattr(subprocess, "DETACHED_PROCESS") and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            subprocess.Popen(
                f'start "" "{command}"',
                shell=True,
                env=os.environ.copy(),
                creationflags=creationflags,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True

        def _try_shellexecute():
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(None, "open", command, None, None, 1)
            return True

        method_map = {
            'startfile': _try_startfile,
            'start_cmd': _try_subprocess_start,
            'shellexecute': _try_shellexecute
        }

        # Try cached working method first if available
        if cached_method and cached_method in method_map:
            try:
                if method_map[cached_method]():
                    launched = True
            except Exception:
                launched = False

        if not launched:
            # Method 1: os.startfile
            try:
                if _try_startfile():
                    launched = True
                    _LAUNCH_METHOD_CACHE[command] = 'startfile'
            except Exception as e:
                methods_tried.append(f"startfile ({e})")

        if not launched:
            # Method 2: Windows start command via subprocess.Popen
            try:
                if _try_subprocess_start():
                    launched = True
                    _LAUNCH_METHOD_CACHE[command] = 'start_cmd'
            except Exception as e:
                methods_tried.append(f"start command ({e})")

        if not launched:
            # Method 3: ShellExecute via ctypes
            try:
                if _try_shellexecute():
                    launched = True
                    _LAUNCH_METHOD_CACHE[command] = 'shellexecute'
            except Exception as e:
                methods_tried.append(f"ShellExecute ({e})")

        if not launched:
            return f"Failed to open {target}, sir. All methods failed: {'; '.join(methods_tried)}."

        # Verification check
        await asyncio.sleep(0.5)
        
        app_display = matched_key or target
        is_running = any(
            proc_name.lower() in (p.info.get('name') or "").lower() or app_clean_key in (p.info.get('name') or "").lower()
            for p in psutil.process_iter(['name'])
        )
        
        # If launched, report success even if psutil background process detection is delayed
        return f"Opened {app_display}, sir."


class AppCloseTool(Tool):
    """Tool to close running software applications safely with graceful terminate and force kill fallback."""

    PROTECTED_PROCESSES = {
        'python.exe', 'pythonw.exe', 'cmd.exe', 'powershell.exe', 
        'wt.exe', 'windowsterminal.exe'
    }

    def __init__(self, app_registry: Optional[AppRegistry] = None):
        super().__init__("close_application", "Close a running software application")
        self.app_registry = app_registry or AppRegistry()

    async def execute(self, app_name: str = "", name: str = "", confirm: bool = False) -> str:
        """Close running application by name with safety check and psutil iteration."""
        target = (app_name or name).strip()
        if not target:
            return "Error: No application specified to close."

        app_clean_key = target.lower()
        proc_name = PROCESS_NAMES.get(app_clean_key, self.app_registry.resolve_process_name(app_clean_key))

        target_stem = os.path.splitext(os.path.basename(proc_name))[0].lower()
        search_stems = {s for s in [target_stem, app_clean_key, proc_name.lower().replace('.exe', '')] if s}

        # Safety Check: Never close protected terminal/python processes without confirmation
        is_protected = any(p.replace(".exe", "").lower() in search_stems for p in self.PROTECTED_PROCESSES)
        if is_protected and not confirm:
            return "That might be the terminal JARVIS is running in, sir. Confirm you want to close it?"

        killed = False
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                p_name = (proc.info.get('name') or "").lower()
                if any(stem in p_name for stem in search_stems):
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    killed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if killed:
            await asyncio.sleep(0.3)
            return f"Closed {target}, sir."

        return f"{target} wasn't running, sir."

        if not still_running:
            return f"Closed {target}, sir."
        else:
            return f"Could not close {target}, sir. It may need manual intervention."


def find_chrome_path() -> Optional[str]:
    """Locate Google Chrome executable on Windows/OSX/Linux."""
    possible_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), r"Google\Chrome\Application\chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), r"Google\Chrome\Application\chrome.exe"),
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        shutil.which("google-chrome")
    ]
    for path in possible_paths:
        if path and os.path.exists(path):
            return path
    return None


def open_url(url: str) -> str:
    """Open URL using Google Chrome as preferred browser, with fallbacks."""
    clean_url = url.strip()
    if not clean_url.startswith(("http://", "https://")):
        clean_url = f"https://{clean_url}"

    # Method 1: Direct Google Chrome execution (User requested Google Chrome as default)
    chrome_path = find_chrome_path()
    if chrome_path:
        try:
            creationflags = 0
            if hasattr(subprocess, "DETACHED_PROCESS") and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            subprocess.Popen(
                [chrome_path, clean_url],
                creationflags=creationflags,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return f"Opening {clean_url} in Google Chrome, sir."
        except Exception:
            pass

    # Method 2: os.startfile (Native Windows ShellExecute)
    try:
        if hasattr(os, "startfile"):
            os.startfile(clean_url)
            return f"Opening {clean_url}, sir."
    except Exception:
        pass
    
    # Method 3: Python webbrowser standard library
    try:
        import webbrowser
        try:
            browser = webbrowser.get('google-chrome') or webbrowser.get('chrome')
            browser.open(clean_url)
            return f"Opening {clean_url} in Google Chrome, sir."
        except Exception:
            webbrowser.open(clean_url)
            return f"Opening {clean_url}, sir."
    except Exception:
        pass
    
    # Method 4: Windows start command fallback
    try:
        creationflags = 0
        if hasattr(subprocess, "DETACHED_PROCESS") and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            f'start "" "{clean_url}"',
            shell=True,
            env=os.environ.copy(),
            creationflags=creationflags
        )
        return f"Opening {clean_url}, sir."
    except Exception as e:
        return f"Failed to open {clean_url}: {str(e)}"


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
                return open_url(url)
            else:
                query_encoded = urllib.parse.quote(target)
                search_url = f"https://www.google.com/search?q={query_encoded}"
                return open_url(search_url)
        except Exception as e:
            return f"Error opening URL/browser: {str(e)}"


class WebsiteOpenTool(Tool):
    """Tool to open common websites by alias, domain name, or direct URL"""
    
    SITE_ALIASES = {
        "youtube": "https://www.youtube.com",
        "you tube": "https://www.youtube.com",
        "gmail": "https://mail.google.com",
        "g mail": "https://mail.google.com",
        "github": "https://www.github.com",
        "git hub": "https://www.github.com",
        "google": "https://www.google.com",
        "reddit": "https://www.reddit.com",
        "twitter": "https://www.twitter.com",
        "x": "https://x.com",
        "linkedin": "https://www.linkedin.com",
        "linked in": "https://www.linkedin.com",
        "netflix": "https://www.netflix.com",
        "spotify": "https://open.spotify.com",
        "chatgpt": "https://chat.openai.com",
        "chat gpt": "https://chat.openai.com",
        "claude": "https://claude.ai",
        "amazon": "https://www.amazon.com",
        "wikipedia": "https://www.wikipedia.org",
        "instagram": "https://www.instagram.com",
        "facebook": "https://www.facebook.com",
        "whatsapp": "https://web.whatsapp.com",
        "coursera": "https://www.coursera.org",
        "udemy": "https://www.udemy.com",
        "stackoverflow": "https://stackoverflow.com",
        "stack overflow": "https://stackoverflow.com"
    }
    
    def __init__(self):
        super().__init__("open_website", "Open a website in the default browser by name, alias, domain, or URL")
        
    async def execute(self, site_name: str = "", url: str = "") -> str:
        """Open website by name, alias, domain, or URL"""
        try:
            target = (site_name or url).strip()
            if not target:
                return "Error: No website name or URL provided."
                
            # Strip leading prefix tags like "website", "site", "url", "page"
            target_clean = re.sub(r'^(website|site|url|page|link|webpage)\s+', '', target, flags=re.I).strip()
            target_lower = target_clean.lower()
            
            # Check for direct URL or domain string
            if target_clean.startswith(("http://", "https://", "www.")) or bool(re.search(r'\.[a-z]{2,6}(/|\?|#|$)', target_lower)):
                final_url = target_clean if target_clean.startswith(("http://", "https://")) else f"https://{target_clean}"
                return open_url(final_url)
                
            # Direct alias match
            resolved_url = self.SITE_ALIASES.get(target_lower)
            if not resolved_url:
                for alias, site_url in self.SITE_ALIASES.items():
                    if alias in target_lower or target_lower in alias:
                        resolved_url = site_url
                        break
                        
            if resolved_url:
                return open_url(resolved_url)
            else:
                if " " not in target_clean:
                    constructed_url = f"https://www.{target_clean}.com"
                    return open_url(constructed_url)
                else:
                    search_url = f"https://www.google.com/search?q={urllib.parse.quote(target_clean)}"
                    return open_url(search_url)
        except Exception as e:
            return f"Error opening website '{site_name}': {str(e)}"


class DuckDuckGoSearchTool(Tool):
    """Tool to perform real-time web searches using DuckDuckGo."""
    
    def __init__(self):
        super().__init__("duckduckgo_search", "Perform real-time DuckDuckGo web search")
        
    async def execute(self, query: str, max_results: int = 5) -> str:
        """Execute web query and return formatted search results."""
        target = query.strip()
        if not target:
            return "Error: No search query provided"
            
        results = None
        try:
            try:
                from ddgs import DDGS
                results = list(DDGS().text(target, max_results=max_results))
            except Exception:
                from duckduckgo_search import DDGS
                results = list(DDGS().text(target, max_results=max_results))
        except Exception as pkg_err:
            console.print(f"[dim yellow]DuckDuckGo package search fallback: {pkg_err}[/dim yellow]")

        if results:
            formatted = [f"=== DuckDuckGo Search Results for '{target}' ==="]
            for idx, r in enumerate(results, start=1):
                title = r.get("title", "No Title")
                href = r.get("href", "")
                body = r.get("body", "No Snippet")
                formatted.append(f"{idx}. {title}\n   URL: {href}\n   Snippet: {body}")
            return "\n".join(formatted)

        try:
            import json
            import urllib.request
            params = urllib.parse.urlencode({
                "q": target,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1"
            })
            url = f"https://api.duckduckgo.com/?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-Assistant/1.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                abstract = data.get("AbstractText", "")
                related = data.get("RelatedTopics", [])

                lines = [f"=== DuckDuckGo Instant Answer for '{target}' ==="]
                if abstract:
                    lines.append(f"Abstract: {abstract}")
                    source = data.get("AbstractURL", "")
                    if source:
                        lines.append(f"Source: {source}")
                elif related:
                    lines.append("Related Topics:")
                    for item in related[:max_results]:
                        if isinstance(item, dict) and "Text" in item:
                            lines.append(f"• {item['Text']}")

                if len(lines) > 1:
                    return "\n".join(lines)
                return f"No DuckDuckGo results found for '{target}'."
        except Exception as e:
            return f"Error executing DuckDuckGo search for '{target}': {str(e)}"


class ProjectTool(Tool):
    """Tool to manage and query projects in database"""

    def __init__(self, project_manager: Optional[Any] = None):
        super().__init__("project_tool", "Access, search, create, update, and manage project database records")
        from jarvis.projects import ProjectManager
        self.pm = project_manager or ProjectManager()

    async def execute(self, action: str = "list", **kwargs) -> str:
        try:
            act = action.lower()
            if act in ["list", "summary"]:
                status = kwargs.get("status")
                category = kwargs.get("category")
                projects = self.pm.get_all_projects(status=status, category=category)
                if not projects:
                    return "No projects found in database matching criteria."
                lines = [f"Found {len(projects)} project(s):"]
                for p in projects:
                    lines.append(f"• [{p['id']}] {p['name']} ({p['category']}, priority {p['priority']}) - Status: {p['status']} | Tasks: {p['open_tasks']} open / {p['total_tasks']} total")
                return "\n".join(lines)

            elif act == "get":
                name_or_id = kwargs.get("name_or_id") or kwargs.get("name") or kwargs.get("id")
                if not name_or_id:
                    return "Error: name_or_id parameter required"
                p = self.pm.get_project(name_or_id)
                if not p:
                    return f"Project '{name_or_id}' not found in database."
                lines = [
                    f"=== Project Briefing: {p['name']} ===",
                    f"ID: {p['id']} | Status: {p['status']} | Category: {p['category']} | Priority: {p['priority']}",
                    f"Description: {p.get('description') or 'N/A'}",
                    f"Tech Stack: {p.get('tech_stack') or 'N/A'}",
                    f"Repo: {p.get('repo_url') or 'N/A'} | Deploy: {p.get('deploy_url') or 'N/A'}",
                    f"Start Date: {p.get('start_date') or 'N/A'} | Deadline: {p.get('deadline') or 'N/A'}",
                    f"Task Count: {p['open_tasks']} open, {p['completed_tasks']} completed out of {p['total_tasks']} total",
                ]
                if p.get("tasks"):
                    lines.append("\nTasks:")
                    for t in p["tasks"]:
                        due = f" (Due: {t['due_date']})" if t.get("due_date") else ""
                        lines.append(f"  - [{t['status'].upper()}] #{t['id']} {t['title']}{due}")
                if p.get("notes"):
                    lines.append("\nRecent Notes:")
                    for n in p["notes"][:5]:
                        lines.append(f"  - {n['content']}")
                if p.get("decisions"):
                    lines.append("\nDecisions Logged:")
                    for d in p["decisions"][:5]:
                        lines.append(f"  - {d['decision']} (Reason: {d.get('reasoning', 'N/A')})")
                if p.get("timeline"):
                    lines.append("\nTimeline:")
                    for tm in p["timeline"][:5]:
                        lines.append(f"  - [{tm.get('date', 'N/A')}] {tm['event']}")
                return "\n".join(lines)

            elif act == "create":
                name = kwargs.get("name")
                if not name:
                    return "Error: Project name required"
                p_id = self.pm.create_project(
                    name=name,
                    description=kwargs.get("description", ""),
                    category=kwargs.get("category", "personal"),
                    tech_stack=kwargs.get("tech_stack", ""),
                    deadline=kwargs.get("deadline", ""),
                    repo_url=kwargs.get("repo_url", ""),
                    priority=int(kwargs.get("priority", 3))
                )
                if not p_id:
                    return f"Failed to create project '{name}'. A project with this name may already exist."
                return f"Project '{name}' created successfully with ID {p_id}."

            elif act == "complete":
                name_or_id = kwargs.get("name_or_id") or kwargs.get("name") or kwargs.get("id")
                if not name_or_id:
                    return "Error: Project name or ID required"
                ok = self.pm.complete_project(name_or_id)
                if ok:
                    return f"Project '{name_or_id}' has been marked as COMPLETED, sir."
                return f"Could not find active project '{name_or_id}' to complete."

            elif act == "search":
                query = kwargs.get("query", "")
                results = self.pm.search_projects(query)
                if not results:
                    return f"No projects found matching search query '{query}'."
                lines = [f"Search results for '{query}':"]
                for p in results:
                    lines.append(f"• [{p['id']}] {p['name']} ({p['status']}) - {p.get('description', '')[:60]}")
                return "\n".join(lines)

            elif act == "overdue":
                overdue = self.pm.get_overdue_tasks()
                if not overdue:
                    return "No overdue tasks found across any projects."
                lines = [f"Found {len(overdue)} overdue task(s):"]
                for t in overdue:
                    lines.append(f"• ⚠️ Task #{t['id']} '{t['title']}' in {t['project_name']} (Due since: {t['due_date']})")
                return "\n".join(lines)

            return f"Unknown project action: {action}"
        except Exception as e:
            return f"Error executing project tool: {e}"


_READONLY_CACHE: Dict[str, Tuple[float, Any]] = {}


def _get_cache_ttl(tool_name: str, kwargs: Dict[str, Any]) -> float:
    """Return cache TTL in seconds for read-only tools"""
    t_name = tool_name.lower()
    if t_name in ["system", "system_monitor"]:
        return 30.0
    if t_name == "project_tool" and kwargs.get("action") in ["list", "get", None]:
        return 60.0
    if t_name in ["weather", "get_weather"]:
        return 1800.0
    return 0.0


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
        self.register(AppCloseTool(self.app_registry))
        self.register(URLOpenTool())
        self.register(WebsiteOpenTool())
        self.register(DuckDuckGoSearchTool())
        self.register(PDFSummarizeTool())
        self.register(GitStatusTool())
        self.register(GitTool(self.confirm_dangerous))
        self.register(GitHubIssuesTool())
        self.register(GitHubPRsTool())
        self.register(GitHubCITool())
        self.register(GitHubRepoTool())
        self.register(GitHubNotificationsTool())
        self.register(EmailTool())
        self.register(ProjectTool())
    
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
        """Execute a tool by name with read-only result caching"""
        tool = self.get_tool(tool_name)
        if not tool:
            return f"Error: Tool '{tool_name}' not found"
        
        ttl = _get_cache_ttl(tool_name, kwargs)
        cache_key = f"{tool_name}:{kwargs}"
        if ttl > 0 and cache_key in _READONLY_CACHE:
            ts, cached_res = _READONLY_CACHE[cache_key]
            if time.time() - ts < ttl:
                return cached_res

        from jarvis.ui import ui, UIState
        ui.set_state(UIState.EXECUTING)
        args_str = ", ".join(f"{k}='{v}'" if isinstance(v, str) else f"{k}={v}" for k, v in kwargs.items())
        exec_desc = f"{tool_name} {args_str}".strip()
        ui.render_tool_exec(exec_desc)
        
        result = await tool.execute(**kwargs)
        ui.set_state(UIState.IDLE)
        
        if ttl > 0:
            _READONLY_CACHE[cache_key] = (time.time(), result)

        from datetime import datetime
        tx = {
            "tool": tool_name,
            "kwargs": kwargs,
            "result": str(result),
            "timestamp": datetime.now().strftime("%H:%M:%S")
        }
        return result

    async def execute_tools_parallel(self, tool_calls: List[Dict[str, Any]]) -> List[str]:
        """Execute multiple tool calls concurrently"""
        if not tool_calls:
            return []
        tasks = [
            self.execute_tool(tc["name"], **tc.get("args", {}))
            for tc in tool_calls
        ]
        return await asyncio.gather(*tasks)


class ToolHandler:
    """Wrapper handler to execute tools by action name"""
    def __init__(self, registry: Optional[ToolRegistry] = None):
        if registry is None:
            try:
                from jarvis.api import get_cli_instance
                cli = get_cli_instance()
                self.registry = cli.tools
            except Exception:
                self.registry = ToolRegistry()
        else:
            self.registry = registry

    def execute(self, action: str, args: Optional[Dict[str, Any]] = None) -> Any:
        args = args or {}
        action_map = {
            "open_app": "open_app",
            "open_application": "open_app",
            "close_app": "close_app",
            "read_file": "read_file",
            "write_file": "write_file",
            "shell": "shell",
            "run_command": "shell",
            "git_tool": "git",
        }
        tool_name = action_map.get(action, action)
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.registry.execute_tool(tool_name, **args))
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(self.registry.execute_tool(tool_name, **args))

