"""
Clean, robust Tool Registry and core system tools for JARVIS.
"""

import os
import sys
import shutil
import subprocess
import urllib.parse
import webbrowser
import re
from datetime import datetime
import psutil
import pyperclip
from typing import Dict, List, Any, Callable, Tuple
from jarvis.github_tool import GitHubTool
from jarvis.mcp_client import ObsidianMCPClient


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
        from jarvis.apps import AppRegistry
        registry = AppRegistry()
        cmd, matches, resolved_name = registry.resolve_app(target_name)
        
        if cmd:
            clean_cmd = cmd.strip('"\'')
            if os.name == 'nt' and os.path.exists(clean_cmd):
                try:
                    os.startfile(clean_cmd)
                    return f"Opened application '{target_name}', sir."
                except Exception:
                    pass
            subprocess.Popen(cmd, shell=True)
            return f"Opened application '{target_name}', sir."
        
        # Windows direct launcher fallback
        if os.name == 'nt':
            try:
                os.startfile(target_name)
                return f"Opened application '{target_name}', sir."
            except Exception:
                pass
        
        subprocess.Popen(target_name, shell=True)
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


DANGEROUS_PATTERNS = [
    # File deletion & directory removal
    r'\brm\b', r'\bdel\b', r'\berase\b', r'\brd\b', r'\brmdir\b', r'\bshred\b',
    # Formatting, disk partitioning & raw write
    r'\bformat\b', r'\bdd\b', r'\bmkfs\b', r'\bfdisk\b', r'\bdiskpart\b', r'\bparted\b',
    # System power state
    r'\bshutdown\b', r'\breboot\b', r'\binit\s+[06]\b', r'\bstop-computer\b', r'\brestart-computer\b',
    # File movement, owner/permission overrides
    r'\bmv\b', r'\bmove\b', r'\bchmod\b', r'\bchown\b', r'\bicacls\b', r'\btakeown\b', r'\bsudo\b',
    # Process killing
    r'\bkill\b', r'\btaskkill\b', r'\bstop-process\b', r'\bpkill\b', r'\bkillall\b',
    # File redirection & overwriting
    r'>', r'>>',
    # Download / arbitrary code execution
    r'\bcurl\b', r'\bwget\b', r'\binvoke-webrequest\b', r'\biwr\b', r'\binvoke-expression\b', r'\biex\b',
    # Registry & service deletion
    r'\breg\s+delete\b', r'\bsc\s+delete\b', r'\bremove-item\b',
    # Destructive git commands
    r'\bgit\s+reset\s+--hard\b', r'\bgit\s+clean\b', r'\bgit\s+push\s+.*--force\b'
]


def _load_tool_config(config_path: str = "config.yaml") -> dict:
    try:
        import yaml
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {
        "tools": {
            "confirm_dangerous": True,
            "log_commands": True
        },
        "memory": {
            "log_file": "jarvis_commands.log"
        }
    }


def _check_dangerous_command(command: str) -> Tuple[bool, List[str]]:
    matched = []
    cmd_lower = command.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd_lower):
            display_name = pattern.replace(r'\b', '').replace(r'\s+', ' ')
            if display_name not in matched:
                matched.append(display_name)
    return len(matched) > 0, matched


def _log_command_execution(command: str, status: str, log_file: str = "jarvis_commands.log"):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] STATUS: {status} | CMD: {command}\n"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"[TOOLS] Warning logging command: {e}")


def run_command(command: str = "", confirm: Any = False, **kwargs) -> str:
    target_cmd = command or kwargs.get("cmd") or kwargs.get("command_string") or ""
    if not target_cmd:
        return "FAILED: No command provided."

    cfg = _load_tool_config()
    tools_cfg = cfg.get("tools", {})
    confirm_dangerous = tools_cfg.get("confirm_dangerous", True)
    log_commands = tools_cfg.get("log_commands", True)
    memory_cfg = cfg.get("memory", {})
    log_file = memory_cfg.get("log_file", "jarvis_commands.log")

    # Check if confirmation is provided in parameters
    confirm_val = confirm if confirm != False else kwargs.get("confirmed") or kwargs.get("confirm") or False
    if isinstance(confirm_val, bool):
        is_confirmed = confirm_val
    elif isinstance(confirm_val, str):
        is_confirmed = confirm_val.lower() in ("true", "yes", "y", "1", "confirmed")
    else:
        is_confirmed = False

    # Check for dangerous command patterns
    is_dangerous, matched_patterns = _check_dangerous_command(target_cmd)

    if is_dangerous and confirm_dangerous and not is_confirmed:
        status_msg = f"BLOCKED (Awaiting confirmation - matched: {', '.join(matched_patterns)})"
        if log_commands:
            _log_command_execution(target_cmd, status_msg, log_file)
        
        return (
            f"CONFIRMATION_REQUIRED: The command '{target_cmd}' contains dangerous operations "
            f"({', '.join(matched_patterns)}). Execution has been blocked. "
            f"Please explicitly confirm execution by re-calling run_command with confirm=True."
        )

    # Execute command
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
        
        status_str = f"EXECUTED (Exit code: {result.returncode}, Confirmed: {is_confirmed})"
        if log_commands:
            _log_command_execution(target_cmd, status_str, log_file)

        output = []
        if stdout:
            output.append(f"STDOUT:\n{stdout}")
        if stderr:
            output.append(f"STDERR:\n{stderr}")
        if not output:
            output.append("Command executed with no output.")
        return "\n".join(output)

    except subprocess.TimeoutExpired:
        if log_commands:
            _log_command_execution(target_cmd, "TIMED_OUT", log_file)
        return "FAILED: Command timed out after 30 seconds."
    except Exception as e:
        if log_commands:
            _log_command_execution(target_cmd, f"ERROR ({str(e)})", log_file)
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


def git_add(files: Any = None, **kwargs) -> str:
    """Stage specific files or all changes (-A) if files is omitted/empty."""
    target_files = files if files is not None else kwargs.get("filepaths") or kwargs.get("file") or kwargs.get("path")
    
    cmd = ["git", "add"]
    if not target_files:
        cmd.append("-A")
        desc = "all changes (-A)"
    else:
        if isinstance(target_files, str):
            target_files = [f.strip("'\" ") for f in target_files.split(",") if f.strip()]
        elif isinstance(target_files, list):
            target_files = [str(f).strip("'\" ") for f in target_files if str(f).strip()]
        else:
            target_files = [str(target_files)]
            
        if not target_files:
            cmd.append("-A")
            desc = "all changes (-A)"
        else:
            cmd.extend(target_files)
            desc = ", ".join(target_files)

    cfg = _load_tool_config()
    log_commands = cfg.get("tools", {}).get("log_commands", True)
    log_file = cfg.get("memory", {}).get("log_file", "jarvis_commands.log")
    cmd_str = " ".join(cmd)

    try:
        res = subprocess.run(cmd, shell=False, capture_output=True, text=True, timeout=30)
        if res.returncode == 0:
            status_msg = f"SUCCESS: Staged {desc}"
            if log_commands:
                _log_command_execution(cmd_str, "EXECUTED (git_add)", log_file)
            return status_msg
        else:
            err_msg = res.stderr.strip() or res.stdout.strip()
            if log_commands:
                _log_command_execution(cmd_str, f"FAILED ({err_msg})", log_file)
            return f"FAILED: git add returned error: {err_msg}"
    except Exception as e:
        if log_commands:
            _log_command_execution(cmd_str, f"ERROR ({str(e)})", log_file)
        return f"FAILED to run git add: {str(e)}"


def git_commit(message: str = "", confirm: Any = False, **kwargs) -> str:
    """Commit staged changes; fail clearly if nothing is staged. Requires confirmation preview."""
    commit_msg = (message or kwargs.get("msg") or kwargs.get("m") or "").strip()
    if not commit_msg:
        return "FAILED: Commit message is required."

    cfg = _load_tool_config()
    tools_cfg = cfg.get("tools", {})
    confirm_dangerous = tools_cfg.get("confirm_dangerous", True)
    log_commands = tools_cfg.get("log_commands", True)
    log_file = cfg.get("memory", {}).get("log_file", "jarvis_commands.log")

    try:
        diff_res = subprocess.run(["git", "diff", "--cached"], shell=False, capture_output=True, text=True, timeout=15)
        staged_diff = diff_res.stdout.strip()
        if not staged_diff:
            return "FAILED: Nothing staged to commit. Use git_add first."
    except Exception as e:
        return f"FAILED checking staged changes: {str(e)}"

    confirm_val = confirm if confirm != False else kwargs.get("confirmed") or kwargs.get("confirm") or False
    if isinstance(confirm_val, bool):
        is_confirmed = confirm_val
    elif isinstance(confirm_val, str):
        is_confirmed = confirm_val.lower() in ("true", "yes", "y", "1", "confirmed")
    else:
        is_confirmed = False

    cmd_str = f'git commit -m "{commit_msg}"'

    if confirm_dangerous and not is_confirmed:
        preview_diff = staged_diff[:1500] + ("\n... [diff truncated]" if len(staged_diff) > 1500 else "")
        status_msg = "BLOCKED (Awaiting commit confirmation)"
        if log_commands:
            _log_command_execution(cmd_str, status_msg, log_file)
        
        return (
            f"CONFIRMATION_REQUIRED: Preparing to commit staged changes.\n"
            f"Commit Message: \"{commit_msg}\"\n\n"
            f"STAGED DIFF PREVIEW:\n{preview_diff}\n\n"
            f"Please confirm execution by re-calling git_commit with confirm=True."
        )

    try:
        res = subprocess.run(["git", "commit", "-m", commit_msg], shell=False, capture_output=True, text=True, timeout=30)
        stdout = res.stdout.strip()
        stderr = res.stderr.strip()
        if res.returncode == 0:
            if log_commands:
                _log_command_execution(cmd_str, "EXECUTED (git_commit)", log_file)
            return f"SUCCESS: Committed changes.\n{stdout}"
        else:
            err = stderr or stdout
            if log_commands:
                _log_command_execution(cmd_str, f"FAILED ({err})", log_file)
            return f"FAILED to commit: {err}"
    except Exception as e:
        if log_commands:
            _log_command_execution(cmd_str, f"ERROR ({str(e)})", log_file)
        return f"FAILED to execute git commit: {str(e)}"


def git_push(remote: str = "origin", branch: str = None, force: bool = False, confirm: Any = False, **kwargs) -> str:
    """Push committed changes to remote repository. force=True ALWAYS requires confirm=True."""
    target_remote = (remote or kwargs.get("remote_name") or "origin").strip()
    target_branch = branch or kwargs.get("branch_name")

    if not target_branch:
        try:
            b_res = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], shell=False, capture_output=True, text=True, timeout=10)
            if b_res.returncode == 0 and b_res.stdout.strip():
                target_branch = b_res.stdout.strip()
        except Exception:
            pass
        if not target_branch:
            target_branch = "main"

    is_force = bool(force or kwargs.get("force_push"))

    cfg = _load_tool_config()
    tools_cfg = cfg.get("tools", {})
    confirm_dangerous = tools_cfg.get("confirm_dangerous", True)
    log_commands = tools_cfg.get("log_commands", True)
    log_file = cfg.get("memory", {}).get("log_file", "jarvis_commands.log")

    confirm_val = confirm if confirm != False else kwargs.get("confirmed") or kwargs.get("confirm") or False
    if isinstance(confirm_val, bool):
        is_confirmed = confirm_val
    elif isinstance(confirm_val, str):
        is_confirmed = confirm_val.lower() in ("true", "yes", "y", "1", "confirmed")
    else:
        is_confirmed = False

    cmd = ["git", "push", target_remote, target_branch]
    if is_force:
        cmd.append("--force")
    cmd_str = " ".join(cmd)

    requires_confirm = is_force or confirm_dangerous

    if requires_confirm and not is_confirmed:
        status_msg = f"BLOCKED (Awaiting push confirmation {'[FORCE PUSH]' if is_force else ''})"
        if log_commands:
            _log_command_execution(cmd_str, status_msg, log_file)
        
        warn_text = " [WARNING: FORCE PUSH WILL OVERWRITE REMOTE HISTORY]" if is_force else ""
        return (
            f"CONFIRMATION_REQUIRED: Preparing to execute '{cmd_str}'{warn_text}.\n"
            f"Target Remote: {target_remote} | Branch: {target_branch}\n"
            f"Please confirm execution by re-calling git_push with confirm=True."
        )

    try:
        res = subprocess.run(cmd, shell=False, capture_output=True, text=True, timeout=30)
        stdout = res.stdout.strip()
        stderr = res.stderr.strip()
        if res.returncode == 0:
            if log_commands:
                _log_command_execution(cmd_str, "EXECUTED (git_push)", log_file)
            return f"SUCCESS: Pushed to {target_remote}/{target_branch}.\n{stderr or stdout}"
        else:
            err = stderr or stdout
            if log_commands:
                _log_command_execution(cmd_str, f"FAILED ({err})", log_file)
            return f"FAILED to push: {err}"
    except Exception as e:
        if log_commands:
            _log_command_execution(cmd_str, f"ERROR ({str(e)})", log_file)
        return f"FAILED to execute git push: {str(e)}"


def _obsidian_grep_search(query: str, vault_path: str, limit: int = 3) -> str:
    """Fallback grep-based search across markdown files in Obsidian vault."""
    if not vault_path or not os.path.exists(vault_path):
        return f"FAILED: Obsidian vault path '{vault_path}' not found."

    query_lower = query.lower()
    keywords = [k.strip() for k in query_lower.split() if len(k.strip()) > 2]
    if not keywords:
        keywords = [query_lower]

    matches = []
    try:
        for root, _, files in os.walk(vault_path):
            for file in files:
                if file.endswith('.md') and not file.endswith('.bak'):
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, vault_path)
                    try:
                        with open(full_p, 'r', encoding='utf-8', errors='replace') as f:
                            text = f.read()
                        text_lower = text.lower()
                        score = sum(text_lower.count(kw) for kw in keywords)
                        if any(kw in file.lower() for kw in keywords):
                            score += 5
                        if score > 0:
                            lines = text.splitlines()
                            snippet_lines = [l for l in lines if any(kw in l.lower() for kw in keywords)]
                            snippet = "\n".join(snippet_lines[:3]) if snippet_lines else text[:200]
                            matches.append({
                                'title': file[:-3],
                                'path': rel_p,
                                'score': score,
                                'snippet': snippet
                            })
                    except Exception:
                        continue
        if not matches:
            return f"No Obsidian notes found matching '{query}' in vault."

        matches.sort(key=lambda x: x['score'], reverse=True)
        top_matches = matches[:limit]
        out_lines = [f"Obsidian Vault Search Results (Fallback - {len(top_matches)} notes):"]
        for m in top_matches:
            out_lines.append(f"\nNote: {m['title']} ({m['path']})\nExcerpt:\n{m['snippet']}")
        return "\n".join(out_lines)
    except Exception as e:
        return f"FAILED: Error searching Obsidian vault: {str(e)}"


def obsidian_semantic_search(query: str = "", limit: int = 3, **kwargs) -> str:
    """Semantic search over Obsidian notes via Smart Connections MCP server with grep fallback."""
    search_query = (query or kwargs.get("q") or kwargs.get("search") or "").strip()
    if not search_query:
        return "FAILED: No query provided for obsidian_semantic_search."

    cfg = _load_tool_config()
    obs_cfg = cfg.get("obsidian", {})
    vault_path = _clean_path(obs_cfg.get("vault_path", "C:/Users/nived/Obsidian/Vault"))
    mcp_url = obs_cfg.get("smart_connections_mcp_url", "http://127.0.0.1:3000")
    limit_num = int(limit) if str(limit).isdigit() else 3

    # Try MCP Client
    try:
        mcp_client = ObsidianMCPClient(mcp_url=mcp_url, timeout=3.0)
        results = mcp_client.search_notes(search_query, limit=limit_num)
        if results:
            out = [f"Obsidian Semantic Memory Search Results ({len(results)} notes via Smart Connections MCP):"]
            for r in results:
                out.append(f"\nNote: {r['title']} ({r.get('path', 'n/a')})\nSimilarity Score: {r.get('score', 0.0):.2f}\nExcerpt:\n{r.get('content', '')}")
            return "\n".join(out)
    except Exception as e:
        print(f"[TOOLS] MCP semantic search unavailable ({e}), using vault fallback...")

    # Fallback to local grep search
    return _obsidian_grep_search(search_query, vault_path, limit=limit_num)


def obsidian_create_note(title: str = "", content: Any = "", folder: str = "", **kwargs) -> str:
    """Create a new markdown note directly in Obsidian vault."""
    note_title = _clean_path(title or kwargs.get("filename") or kwargs.get("name") or kwargs.get("note_title") or kwargs.get("note_name") or kwargs.get("file") or kwargs.get("title_or_filename"))
    
    note_content = content
    if note_content == "":
        note_content = kwargs.get("text") or kwargs.get("body") or kwargs.get("note_content") or kwargs.get("data") or ""
        
    folder_path = _clean_path(folder or kwargs.get("dir") or kwargs.get("subfolder") or kwargs.get("directory") or kwargs.get("folder_path") or "")

    if not note_title:
        return "FAILED: Note title/filename is required."
    if not isinstance(note_content, str):
        note_content = str(note_content)

    if not note_title.lower().endswith(".md"):
        note_title += ".md"

    cfg = _load_tool_config()
    vault_path = _clean_path(cfg.get("obsidian", {}).get("vault_path", "C:/Users/nived/Obsidian/Vault"))
    if not vault_path:
        return "FAILED: Obsidian vault_path not configured in config.yaml."

    try:
        target_dir = os.path.join(vault_path, folder_path) if folder_path else vault_path
        os.makedirs(target_dir, exist_ok=True)
        full_path = os.path.join(target_dir, note_title)

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(note_content)

        if os.path.exists(full_path):
            size = os.path.getsize(full_path)
            return f"SUCCESS: Created Obsidian note '{full_path}' ({size} bytes)"
        return f"FAILED: Obsidian note '{full_path}' was not created."
    except Exception as e:
        return f"FAILED to create Obsidian note: {str(e)}"


def obsidian_daily_note(content: Any = "", heading: str = "", **kwargs) -> str:
    """Create or append content to today's Obsidian daily note."""
    note_content = content
    if note_content == "":
        note_content = kwargs.get("text") or kwargs.get("body") or kwargs.get("note_content") or kwargs.get("entry") or ""
        
    note_heading = (heading or kwargs.get("title") or kwargs.get("section") or kwargs.get("header") or "").strip()
    if not isinstance(note_content, str):
        note_content = str(note_content)

    cfg = _load_tool_config()
    vault_path = _clean_path(cfg.get("obsidian", {}).get("vault_path", "C:/Users/nived/Obsidian/Vault"))
    if not vault_path:
        return "FAILED: Obsidian vault_path not configured in config.yaml."

    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        daily_dir = os.path.join(vault_path, "Daily")
        os.makedirs(daily_dir, exist_ok=True)
        daily_path = os.path.join(daily_dir, f"{today_str}.md")

        mode = 'a' if os.path.exists(daily_path) else 'w'
        with open(daily_path, mode, encoding='utf-8') as f:
            if mode == 'w':
                f.write(f"# Daily Note - {today_str}\n\n")
            if note_heading:
                f.write(f"## {note_heading}\n")
            f.write(f"{note_content}\n\n")

        size = os.path.getsize(daily_path)
        return f"SUCCESS: Updated Obsidian Daily Note '{daily_path}' ({size} bytes)"
    except Exception as e:
        return f"FAILED to update Obsidian daily note: {str(e)}"


def obsidian_edit_note(filepath: str = "", content: Any = "", append: bool = False, **kwargs) -> str:
    """Edit an existing note in Obsidian vault with automatic .bak backup creation."""
    target_path = _clean_path(filepath or kwargs.get("filename") or kwargs.get("title") or kwargs.get("path") or kwargs.get("name") or kwargs.get("note_name") or kwargs.get("note_title"))
    
    note_content = content
    if note_content == "":
        note_content = kwargs.get("text") or kwargs.get("body") or kwargs.get("new_content") or kwargs.get("note_content") or ""
        
    is_append = bool(append or kwargs.get("append_mode") or kwargs.get("is_append") or kwargs.get("append_text"))

    if not target_path:
        return "FAILED: Note filepath is required for obsidian_edit_note."
    if not isinstance(note_content, str):
        note_content = str(note_content)

    cfg = _load_tool_config()
    vault_path = _clean_path(cfg.get("obsidian", {}).get("vault_path", "C:/Users/nived/Obsidian/Vault"))

    if not os.path.isabs(target_path) and vault_path:
        full_path = os.path.join(vault_path, target_path)
    else:
        full_path = target_path

    if not full_path.lower().endswith(".md"):
        full_path += ".md"

    try:
        full_path = os.path.abspath(full_path)
        if not os.path.exists(full_path):
            return f"FAILED: Note '{full_path}' does not exist."

        # Automatic backup creation before editing
        backup_path = f"{full_path}.bak"
        shutil.copy2(full_path, backup_path)

        mode = 'a' if is_append else 'w'
        with open(full_path, mode, encoding='utf-8') as f:
            if is_append:
                f.write(f"\n{note_content}")
            else:
                f.write(note_content)

        size = os.path.getsize(full_path)
        action_word = "Appended to" if is_append else "Edited"
        return f"SUCCESS: {action_word} Obsidian note '{full_path}' ({size} bytes). Backup saved at '{backup_path}'."
    except Exception as e:
        return f"FAILED to edit Obsidian note: {str(e)}"


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
            "description": "Execute a shell command and return its output. Dangerous operations (rm, del, mv, kill, shutdown, curl, >, etc.) require confirm=True.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command string to execute"},
                    "confirm": {"type": "boolean", "description": "Set to true to explicitly confirm execution of dangerous operations"}
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
            "name": "git_add",
            "description": "Stage files for Git commit. Omit files or pass empty to stage all changes (-A).",
            "parameters": {
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of file paths to stage. Omit to stage all changes (-A)."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Commit staged changes with a commit message. Shows staged diff and requires confirm=True.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message"},
                    "confirm": {"type": "boolean", "description": "Set to true to confirm commit execution after previewing diff"}
                },
                "required": ["message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_push",
            "description": "Push committed changes to remote repository. Force push ALWAYS requires confirm=True.",
            "parameters": {
                "type": "object",
                "properties": {
                    "remote": {"type": "string", "description": "Remote name (default: 'origin')"},
                    "branch": {"type": "string", "description": "Branch name (default: current branch)"},
                    "force": {"type": "boolean", "description": "Set to true for force push (ALWAYS requires confirm=True)"},
                    "confirm": {"type": "boolean", "description": "Set to true to confirm push execution"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obsidian_semantic_search",
            "description": "Perform local semantic memory search over Obsidian notes via Smart Connections MCP server (with vault grep fallback).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "limit": {"type": "integer", "description": "Max number of relevant notes to return (default: 3)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obsidian_create_note",
            "description": "Create a new Markdown note directly in Obsidian vault.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Title or filename of note"},
                    "content": {"type": "string", "description": "Markdown content for the note"},
                    "folder": {"type": "string", "description": "Optional subfolder inside vault"}
                },
                "required": ["title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obsidian_daily_note",
            "description": "Create or append content to today's Obsidian daily note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Text content to append to daily note"},
                    "heading": {"type": "string", "description": "Optional section heading"}
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obsidian_edit_note",
            "description": "Edit an existing note in Obsidian vault with automatic .bak backup file creation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Path or filename of target note"},
                    "content": {"type": "string", "description": "New content or text to append"},
                    "append": {"type": "boolean", "description": "Set to true to append to existing note instead of overwriting"}
                },
                "required": ["filepath", "content"]
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
            ("git_add", git_add),
            ("git_commit", git_commit),
            ("git_push", git_push),
            ("obsidian_semantic_search", obsidian_semantic_search),
            ("obsidian_create_note", obsidian_create_note),
            ("obsidian_daily_note", obsidian_daily_note),
            ("obsidian_edit_note", obsidian_edit_note),
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
