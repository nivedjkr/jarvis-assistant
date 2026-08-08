import os
import subprocess
import time
import psutil
import webbrowser
import inspect
from pydantic import BaseModel, ValidationError

def validate_tool_schemas(registry):
    errors = []
    for name, func in registry.tools.items():
        # Get schema for this tool
        schema = next(
            (s for s in registry.schemas 
             if s.get('function', {}).get('name') == name), 
            None
        )
        if not schema:
            errors.append(f"No schema for tool: {name}")
            continue
        
        # Check function is callable
        if not callable(func):
            errors.append(f"Tool not callable: {name}")
            continue
        
        # Check required params exist in function
        sig = inspect.signature(func)
        schema_params = schema['function']['parameters']\
            .get('properties', {}).keys()
        func_params = sig.parameters.keys()
        
        for param in schema['function']['parameters']\
            .get('required', []):
            if param not in func_params:
                errors.append(
                    f"Tool {name}: required param "
                    f"'{param}' not in function signature"
                )
    
    if errors:
        print("[SCHEMA] Validation errors:")
        for e in errors:
            try:
                print(f"  ✗ {e}")
            except UnicodeEncodeError:
                print(f"  [X] {e}")
        return False
    else:
        try:
            print(f"[SCHEMA] All {len(registry.tools)} "
                  f"tool schemas valid ✓")
        except UnicodeEncodeError:
            print(f"[SCHEMA] All {len(registry.tools)} "
                  f"tool schemas valid [OK]")
        return True

DANGEROUS_KEYWORDS = [
    "rm", "del", "format", "shutdown", "reboot", "dd", "mkfs", "fdisk",
    "mv", "chmod", "kill", ">", ">>", "curl", "wget"
]

def _load_config():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config.yaml")
    if not os.path.exists(config_path):
        config_path = "config.yaml"
    if os.path.exists(config_path):
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}

def _log_command(command: str, confirmed: bool):
    try:
        cfg = _load_config()
        if not cfg.get("tools", {}).get("log_commands", True):
            return
        log_rel = cfg.get("memory", {}).get("log_file", "jarvis_commands.log")
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_path = os.path.join(base_dir, log_rel)
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] Command: '{command}' | Confirmed: {confirmed}\n")
    except Exception:
        pass

def _is_dangerous_command(command: str):
    import re
    cmd_str = command.strip()
    if ">>" in cmd_str:
        return True, ">>"
    if ">" in cmd_str:
        return True, ">"
        
    word_keywords = ["rm", "del", "format", "shutdown", "reboot", "dd", "mkfs", "fdisk", "mv", "chmod", "kill", "curl", "wget"]
    pattern = r'\b(' + '|'.join(re.escape(k) for k in word_keywords) + r')\b'
    match = re.search(pattern, cmd_str, re.IGNORECASE)
    if match:
        return True, match.group(1)
        
    return False, ""

def _get_repo_path(path: str = "") -> str:
    if path and os.path.exists(path):
        return path
    try:
        r_top = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True, text=True, timeout=5, cwd=os.getcwd()
        )
        if r_top.returncode == 0 and r_top.stdout.strip():
            return r_top.stdout.strip()
    except Exception:
        pass
    cfg = _load_config()
    cfg_path = cfg.get("github", {}).get("repo_path")
    if cfg_path and os.path.exists(cfg_path):
        return cfg_path
    return os.getcwd()

class ToolRegistry:
    def __init__(self):
        self.tools = {}   # name -> async callable
        self.schemas = [] # OpenAI tool schemas
        self._register_all()
        # Validate schemas on startup
        validate_tool_schemas(self)
    
    def _register_all(self):
        self._register_file_tools()
        self._register_app_tools()
        self._register_browser_tools()
        self._register_system_tools()
        self._register_clipboard_tools()
        self._register_github_tools()
        self._register_github_full_tools()
        self._register_system_file_tools()
        self._register_semantic_memory_tools()
        print(f"[TOOLS] Registered {len(self.tools)} tools: "
              f"{list(self.tools.keys())}")
    
    def _add(self, name: str, func, 
              description: str, props: dict, 
              required: list = None):
        self.tools[name] = func
        schema_obj = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required or list(props.keys())
                }
            }
        }
        for idx, item in enumerate(self.schemas):
            if item.get("function", {}).get("name") == name:
                self.schemas[idx] = schema_obj
                return
        self.schemas.append(schema_obj)
    
    async def execute(self, name: str, args: dict) -> str:
        if name not in self.tools:
            return f"Unknown tool: {name}"
        try:
            fn = self.tools[name]
            import asyncio, inspect
            if inspect.iscoroutinefunction(fn):
                result = await fn(**args)
            else:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, lambda: fn(**args)
                )
            return str(result) if result else "Done."
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Tool error: {str(e)}"
    
    def _register_file_tools(self):
        
        def write_file(path: str, content: str) -> str:
            try:
                full = os.path.abspath(path)
                os.makedirs(
                    os.path.dirname(full) or '.', 
                    exist_ok=True
                )
                with open(full, 'w', encoding='utf-8') as f:
                    f.write(content)
                if not os.path.exists(full):
                    return f"FAILED: {path} not created"
                size = os.path.getsize(full)
                return f"Created: {full} ({size} bytes)"
            except Exception as e:
                return f"FAILED: {e}"
        
        def read_file(path: str) -> str:
            try:
                full = os.path.abspath(path)
                if not os.path.exists(full):
                    return f"FAILED: {path} not found"
                with open(full, 'r', encoding='utf-8') as f:
                    content = f.read()
                return f"Contents of {path}:\n{content}" \
                       if content else f"Empty file: {full}"
            except Exception as e:
                return f"FAILED: {e}"
        
        def list_files(path: str = '.') -> str:
            try:
                full = os.path.abspath(path)
                if not os.path.exists(full):
                    return f"FAILED: {path} not found"
                items = os.listdir(full)
                if not items:
                    return f"Empty: {full}"
                lines = []
                for item in sorted(items):
                    tag = "[DIR]" if os.path.isdir(
                        os.path.join(full, item)) else "[FILE]"
                    lines.append(f"{tag} {item}")
                return f"Contents of {path}:\n" + \
                       "\n".join(lines)
            except Exception as e:
                return f"FAILED: {e}"
        
        def create_directory(path: str) -> str:
            try:
                full = os.path.abspath(path)
                os.makedirs(full, exist_ok=True)
                return f"Created directory: {full}" \
                       if os.path.exists(full) \
                       else "FAILED: not created"
            except Exception as e:
                return f"FAILED: {e}"
        
        def delete_file(path: str) -> str:
            try:
                import shutil
                full = os.path.abspath(path)
                if not os.path.exists(full):
                    return f"FAILED: {path} not found"
                if os.path.isdir(full):
                    shutil.rmtree(full)
                else:
                    os.remove(full)
                return f"Deleted: {full}"
            except Exception as e:
                return f"FAILED: {e}"
        
        self._add("write_file", write_file,
            "Write/create a file. Call this when user asks "
            "to create or save a file. Never confirm without "
            "calling this tool.",
            {"path": {"type": "string", 
                      "description": "File path"},
             "content": {"type": "string",
                         "description": "File content"}})
        
        self._add("read_file", read_file,
            "Read real file contents from disk.",
            {"path": {"type": "string",
                      "description": "File path to read"}})
        
        self._add("list_files", list_files,
            "List files in a directory.",
            {"path": {"type": "string",
                      "description": "Directory path",
                      "default": "."}},
            required=[])
        
        self._add("create_directory", create_directory,
            "Create a new folder/directory.",
            {"path": {"type": "string",
                      "description": "Directory path"}})
        
        self._add("delete_file", delete_file,
            "Delete a file or directory.",
            {"path": {"type": "string",
                      "description": "Path to delete"}})
    
    def _register_app_tools(self):
        APP_MAP = {
            'notepad':     'notepad.exe',
            'calculator':  'calc.exe',
            'chrome':      'chrome.exe',
            'vscode':      'code',
            'code':        'code',
            'explorer':    'explorer.exe',
            'spotify':     'spotify.exe',
            'discord':     'discord.exe',
            'telegram':    'telegram.exe',
            'paint':       'mspaint.exe',
            'word':        'winword.exe',
            'excel':       'excel.exe',
            'powershell':  'powershell.exe',
            'cmd':         'cmd.exe',
            'taskmgr':     'taskmgr.exe',
        }
        
        def open_application(name: str) -> str:
            n = name.lower().strip()
            command = APP_MAP.get(n, name)
            
            # Method 1: os.startfile
            try:
                os.startfile(command)
                time.sleep(1.5)
                return f"Opened {name}, sir."
            except Exception:
                pass
            
            # Method 2: Windows start
            try:
                subprocess.Popen(
                    f'start "" "{command}"',
                    shell=True,
                    env=os.environ.copy(),
                    creationflags=(
                        subprocess.DETACHED_PROCESS |
                        subprocess.CREATE_NEW_PROCESS_GROUP
                    )
                )
                time.sleep(1.5)
                return f"Opened {name}, sir."
            except Exception:
                pass
            
            # Method 3: ShellExecute
            try:
                import ctypes
                ctypes.windll.shell32.ShellExecuteW(
                    None, "open", command, None, None, 1
                )
                return f"Opened {name}, sir."
            except Exception as e:
                return f"FAILED to open {name}: {e}"
        
        def close_application(name: str) -> str:
            PROTECTED = ['python.exe', 'pythonw.exe']
            n = name.lower()
            proc_name = APP_MAP.get(n, name)
            
            if proc_name.lower() in PROTECTED:
                return "That's my own process, sir."
            
            killed = False
            target = proc_name.lower()
            for proc in psutil.process_iter(['name']):
                try:
                    proc_name_lower = proc.info['name'].lower()
                    # Exact match or prefix match (e.g., 'notepad.exe' matches 'notepad.exe')
                    if proc_name_lower == target or proc_name_lower.startswith(target + '.'):
                        proc.terminate()
                        killed = True
                except:
                    pass
            
            if killed:
                time.sleep(1.5)
                return f"Closed {name}, sir."
            return f"{name} wasn't running, sir."
        
        def open_file_with_app(
            app: str, filepath: str) -> str:
            try:
                full = os.path.abspath(filepath)
                if not os.path.exists(full):
                    return f"FAILED: {filepath} not found"
                subprocess.Popen(
                    [APP_MAP.get(app.lower(), app), full],
                    env=os.environ.copy()
                )
                return f"Opened {filepath} with {app}, sir."
            except Exception as e:
                return f"FAILED: {e}"
        
        self._add("open_application", open_application,
            "Open an application. Call when user says "
            "open/launch/start an app. Never confirm "
            "without calling this.",
            {"name": {"type": "string",
                      "description": "App name: notepad, "
                      "chrome, vscode, calculator, spotify, "
                      "discord, telegram, explorer, etc"}})
        
        self._add("close_application", close_application,
            "Close a running application.",
            {"name": {"type": "string",
                      "description": "App name to close"}})
        
        self._add("open_file_with_app", open_file_with_app,
            "Open a file with a specific application.",
            {"app": {"type": "string",
                     "description": "App name"},
             "filepath": {"type": "string",
                          "description": "File to open"}})
    
    def _register_browser_tools(self):
        SITES = {
            'youtube':   'https://www.youtube.com',
            'gmail':     'https://mail.google.com',
            'github':    'https://www.github.com',
            'google':    'https://www.google.com',
            'reddit':    'https://www.reddit.com',
            'twitter':   'https://www.twitter.com',
            'x':         'https://www.x.com',
            'linkedin':  'https://www.linkedin.com',
            'netflix':   'https://www.netflix.com',
            'spotify':   'https://open.spotify.com',
            'claude':    'https://claude.ai',
            'chatgpt':   'https://chat.openai.com',
            'notion':    'https://www.notion.so',
            'figma':     'https://www.figma.com',
            'stackoverflow': 'https://stackoverflow.com',
        }
        
        def open_url(url: str) -> str:
            try:
                if not url.startswith('http'):
                    url = 'https://' + url
                subprocess.Popen(
                    f'start "" "{url}"',
                    shell=True,
                    env=os.environ.copy()
                )
                return f"Opening {url}, sir."
            except Exception as e:
                try:
                    webbrowser.open(url)
                    return f"Opening {url}, sir."
                except:
                    return f"FAILED: {e}"
        
        GREETINGS = {'hey', 'hello', 'hi', 'hey jarvis', 'jarvis', 'thanks', 'thank you', 'ok', 'okay'}
        
        def open_website(site: str) -> str:
            s = site.lower().strip()
            if s in GREETINGS:
                return "Greeting acknowledged."
            url = SITES.get(s)
            if url:
                return open_url(url)
            if '.' in site:
                return open_url(site)
            return f"Not a valid website name or URL. Use web_search for Google searches."
        
        def web_search(query: str) -> str:
            q = query.strip()
            if q.lower() in GREETINGS:
                return "Greeting acknowledged."
            q_url = q.replace(' ', '+')
            return open_url(
                f'https://www.google.com/search?q={q_url}')
        
        self._add("open_url", open_url,
            "Open a URL in the browser.",
            {"url": {"type": "string",
                     "description": "URL to open"}})
        
        self._add("open_website", open_website,
            "Open a specific website by name (youtube, github, gmail, google, reddit, twitter, linkedin, netflix, spotify, etc) or domain URL. Do NOT call for greetings or casual chat.",
            {"site": {"type": "string",
                      "description": "Site name or domain URL"}})
        
        self._add("web_search", web_search,
            "Search Google for explicit user search queries. Do NOT call for greetings, hi, or casual chat.",
            {"query": {"type": "string",
                       "description": "Search terms"}})
    
    def _register_system_tools(self):
        
        def run_command(command: str, confirmed: bool = False) -> str:
            cfg = _load_config()
            confirm_dangerous = cfg.get("tools", {}).get("confirm_dangerous", True)
            
            is_danger, matched_kw = _is_dangerous_command(command)
            if confirm_dangerous and is_danger and not confirmed:
                return (
                    f"CONFIRMATION REQUIRED: Running '{command}' contains potentially dangerous operation "
                    f"('{matched_kw}'). Reply with 'confirm' or re-run with confirmed=True to proceed."
                )
            
            try:
                result = subprocess.run(
                    command, shell=True,
                    capture_output=True, text=True,
                    timeout=30, env=os.environ.copy()
                )
                _log_command(command, confirmed=confirmed or (not is_danger))
                out = result.stdout or result.stderr
                return out[:2000] if out \
                       else "Command completed, no output."
            except subprocess.TimeoutExpired:
                _log_command(command, confirmed=confirmed)
                return "Command timed out."
            except Exception as e:
                _log_command(command, confirmed=confirmed)
                return f"FAILED: {e}"
        
        def get_system_status() -> str:
            try:
                cpu = psutil.cpu_percent(interval=1)
                ram = psutil.virtual_memory()
                disk = psutil.disk_usage('C:\\')
                return (f"CPU: {cpu}%  |  "
                        f"RAM: {ram.percent}% "
                        f"({ram.used//1024//1024}MB)  |  "
                        f"Disk C: {disk.percent}% used")
            except Exception as e:
                return f"FAILED: {e}"
        
        self._add("run_command", run_command,
            "Run a real shell command on the host OS. "
            "Requires confirmation for dangerous commands.",
            {"command": {"type": "string",
                         "description": "Shell command to execute"},
             "confirmed": {"type": "boolean",
                          "default": False,
                          "description": "Set to true after explicit user confirmation"}},
            required=["command"])
        
        self._add("get_system_status", get_system_status,
            "Get real CPU, RAM, and disk usage.",
            {}, required=[])
    
    def _register_clipboard_tools(self):
        
        def copy_to_clipboard(text: str) -> str:
            # Try pyperclip first
            try:
                import pyperclip
                pyperclip.copy(text)
                verify = pyperclip.paste()
                if verify == text:
                    return (f"Copied to clipboard: "
                            f"{text[:80]}")
                return "FAILED: verification mismatch"
            except ImportError:
                pass
            
            # Fallback: Windows clip command
            try:
                proc = subprocess.Popen(
                    'clip', stdin=subprocess.PIPE,
                    shell=True
                )
                proc.communicate(
                    text.encode('utf-16-le'))
                return f"Copied to clipboard: {text[:80]}"
            except Exception as e:
                return f"FAILED: {e}"
        
        def paste_from_clipboard() -> str:
            try:
                import pyperclip
                text = pyperclip.paste()
                return f"Clipboard: {text}" \
                       if text else "Clipboard empty."
            except Exception as e:
                return f"FAILED: {e}"
        
        self._add("copy_to_clipboard", copy_to_clipboard,
            "Copy text to clipboard. Always call this "
            "when user asks to copy something.",
            {"text": {"type": "string",
                      "description": "Text to copy"}})
        
        self._add("paste_from_clipboard",
            paste_from_clipboard,
            "Get current clipboard contents.",
            {}, required=[])
    
    def _register_github_tools(self):
        
        def gh_list_repos(limit: int = 10) -> str:
            result = subprocess.run(
                ['gh', 'repo', 'list',
                 '--limit', str(limit),
                 '--json', 'name,description,isPrivate,url'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                return f"FAILED: {result.stderr}"
            try:
                repos = json.loads(result.stdout)
                lines = [
                    f"{'[private]' if r['isPrivate'] else '[public]'}"
                    f" {r['name']}"
                    for r in repos
                ]
                return "Your repos:\n" + "\n".join(lines)
            except:
                return result.stdout
        
        def gh_list_issues(
            repo: str = "nivedjkr/jarvis-assistant",
            state: str = "open") -> str:
            result = subprocess.run(
                ['gh', 'issue', 'list',
                 '--repo', repo,
                 '--state', state,
                 '--limit', '10',
                 '--json', 'number,title,state'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                return f"FAILED: {result.stderr}"
            try:
                issues = json.loads(result.stdout)
                if not issues:
                    return f"No {state} issues in {repo}"
                lines = [f"#{i['number']} {i['title']}"
                         for i in issues]
                return "\n".join(lines)
            except:
                return result.stdout
        
        def gh_ci_status(
            repo: str = "nivedjkr/jarvis-assistant"
        ) -> str:
            result = subprocess.run(
                ['gh', 'run', 'list',
                 '--repo', repo,
                 '--limit', '3',
                 '--json', 'name,status,conclusion,url'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                return f"FAILED: {result.stderr}"
            try:
                runs = json.loads(result.stdout)
                if not runs:
                    return "No CI runs found."
                r = runs[0]
                c = r.get('conclusion', 'in_progress')
                icon = '✓' if c == 'success' else '✗'
                return (f"Latest CI: {icon} "
                        f"{c.upper()} — {r['name']}")
            except:
                return result.stdout
        
        def gh_create_issue(
            title: str, body: str = "",
            repo: str = "nivedjkr/jarvis-assistant"
        ) -> str:
            cmd = ['gh', 'issue', 'create',
                   '--repo', repo,
                   '--title', title]
            if body:
                cmd += ['--body', body]
            result = subprocess.run(
                cmd, capture_output=True,
                text=True, timeout=15
            )
            if result.returncode != 0:
                return f"FAILED: {result.stderr}"
            return f"Issue created: {result.stdout.strip()}"
        
        self._add("gh_list_repos", gh_list_repos,
            "List your GitHub repositories.",
            {"limit": {"type": "integer",
                       "description": "Max repos to show",
                       "default": 10}},
            required=[])
        
        self._add("gh_list_issues", gh_list_issues,
            "List GitHub issues for a repo.",
            {"repo": {"type": "string",
                      "description": "owner/repo",
                      "default": "nivedjkr/jarvis-assistant"},
             "state": {"type": "string",
                       "description": "open or closed",
                       "default": "open"}},
            required=[])
        
        self._add("gh_ci_status", gh_ci_status,
            "Check GitHub CI/Actions status.",
            {"repo": {"type": "string",
                      "description": "owner/repo",
                      "default": "nivedjkr/jarvis-assistant"}},
            required=[])
        
        self._add("gh_create_issue", gh_create_issue,
            "Create a GitHub issue.",
            {"title": {"type": "string",
                       "description": "Issue title"},
             "body": {"type": "string",
                      "description": "Issue body",
                      "default": ""},
             "repo": {"type": "string",
                      "description": "owner/repo",
                      "default": 
                      "nivedjkr/jarvis-assistant"}},
            required=["title"])

    def _register_github_full_tools(self):
        import subprocess
        import json
        import os
        
        DEFAULT_REPO = "nivedjkr/jarvis-assistant"
        
        # === ACCOUNT & REPOS ===
        def gh_list_repos(limit: int = 20) -> str:
            r = subprocess.run(
                ['gh', 'repo', 'list', '--limit', str(limit),
                 '--json', 'name,description,isPrivate,'
                          'url,pushedAt'],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode != 0: return f"FAILED: {r.stderr}"
            repos = json.loads(r.stdout)
            lines = [
                f"{'[private]' if x['isPrivate'] else '[public]'}"
                f" {x['name']} — "
                f"{x.get('description') or 'no description'}"
                for x in repos
            ]
            return "Your GitHub repos:\n" + "\n".join(lines)
        
        def gh_create_repo(
            name: str, private: bool = False,
            description: str = "") -> str:
            cmd = ['gh', 'repo', 'create', name,
                   '--' + ('private' if private else 'public')]
            if description:
                cmd += ['--description', description]
            cmd += ['--confirm']
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            return r.stdout.strip() if r.returncode == 0 \
                   else f"FAILED: {r.stderr}"
        
        def gh_delete_repo(repo: str) -> str:
            r = subprocess.run(
                ['gh', 'repo', 'delete', repo, '--yes'],
                capture_output=True, text=True, timeout=15
            )
            return f"Deleted {repo}" if r.returncode == 0 \
                   else f"FAILED: {r.stderr}"
        
        def gh_clone_repo(
            repo: str, path: str = '.') -> str:
            r = subprocess.run(
                ['gh', 'repo', 'clone', repo, path],
                capture_output=True, text=True, timeout=60
            )
            return f"Cloned to {path}" if r.returncode == 0 \
                   else f"FAILED: {r.stderr}"
        
        def gh_repo_info(
            repo: str = "nivedjkr/jarvis-assistant") -> str:
            r = subprocess.run(
                ['gh', 'repo', 'view', repo,
                 '--json', 'name,description,stargazerCount,'
                          'forks,openIssues,url,'
                          'defaultBranchRef,isPrivate'],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode != 0: return f"FAILED: {r.stderr}"
            d = json.loads(r.stdout)
            return (f"{d['name']}: {d.get('description','')}\n"
                    f"Stars: {d['stargazerCount']} | "
                    f"Forks: {d['forks']} | "
                    f"Open issues: {d['openIssues']}\n"
                    f"URL: {d['url']}")
        
        # === GIT OPERATIONS ===
        def git_add_commit_push(
            message: str,
            path: str = "",
            confirmed: bool = False) -> str:
            
            target_path = _get_repo_path(path)
            
            # Step 1: git add .
            r1 = subprocess.run(
                ['git', 'add', '.'],
                capture_output=True, text=True, cwd=target_path, env=os.environ.copy()
            )
            if r1.returncode != 0:
                return f"FAILED at git add: {r1.stderr}"
            
            # Step 2: git diff --cached --stat
            r_diff = subprocess.run(
                ['git', 'diff', '--cached', '--stat'],
                capture_output=True, text=True, cwd=target_path, env=os.environ.copy()
            )
            diff_stat = r_diff.stdout.strip()
            
            # Check if there's anything staged
            r_check = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True, text=True, cwd=target_path, env=os.environ.copy()
            )
            if not r_check.stdout.strip():
                return "Nothing to commit, sir."
            
            # Step 3: Confirmation check
            if not confirmed:
                return (
                    f"Staged changes:\n{diff_stat}\n\n"
                    f"CONFIRMATION REQUIRED: Please confirm committing and pushing with message: '{message}'. Re-run with confirmed=True to proceed."
                )
            
            # Step 4: git commit
            r2 = subprocess.run(
                ['git', 'commit', '-m', message],
                capture_output=True, text=True, cwd=target_path, env=os.environ.copy()
            )
            if r2.returncode != 0:
                if "nothing to commit" in (r2.stdout + r2.stderr).lower():
                    return "Nothing to commit, sir."
                return f"FAILED at git commit: {r2.stderr}"
            
            # Step 5: git push
            r3 = subprocess.run(
                ['git', 'push'],
                capture_output=True, text=True, cwd=target_path, env=os.environ.copy()
            )
            if r3.returncode != 0:
                return f"FAILED at git push: {r3.stderr}\nCommitted locally but not pushed."
            
            _log_command(f"git commit -m '{message}' && git push", confirmed=True)
            return f"✓ Staged changes\n✓ Committed: {message}\n✓ Pushed to GitHub"
        
        def git_status(path: str = "") -> str:
            target_path = _get_repo_path(path)
            r = subprocess.run(
                ['git', 'status'],
                capture_output=True, text=True, cwd=target_path
            )
            return r.stdout if r.returncode == 0 \
                   else f"FAILED: {r.stderr}"
        
        def git_pull(path: str = "") -> str:
            target_path = _get_repo_path(path)
            r = subprocess.run(
                ['git', 'pull'],
                capture_output=True, text=True, cwd=target_path
            )
            return r.stdout if r.returncode == 0 \
                   else f"FAILED: {r.stderr}"
        
        def git_log(
            limit: int = 10,
            path: str = "") -> str:
            target_path = _get_repo_path(path)
            r = subprocess.run(
                ['git', 'log', '--oneline', f'-{limit}'],
                capture_output=True, text=True, cwd=target_path
            )
            return r.stdout if r.returncode == 0 \
                   else f"FAILED: {r.stderr}"
        
        def git_diff(path: str = "") -> str:
            target_path = _get_repo_path(path)
            r = subprocess.run(
                ['git', 'diff', '--stat'],
                capture_output=True, text=True, cwd=target_path
            )
            return r.stdout or "No changes." \
                   if r.returncode == 0 else f"FAILED: {r.stderr}"
        
        def git_create_branch(
            branch: str,
            path: str = "") -> str:
            target_path = _get_repo_path(path)
            r = subprocess.run(
                ['git', 'checkout', '-b', branch],
                capture_output=True, text=True, cwd=target_path
            )
            return f"Created branch: {branch}" \
                   if r.returncode == 0 else f"FAILED: {r.stderr}"
        
        def git_switch_branch(
            branch: str,
            path: str = "") -> str:
            target_path = _get_repo_path(path)
            r = subprocess.run(
                ['git', 'checkout', branch],
                capture_output=True, text=True, cwd=target_path
            )
            return f"Switched to: {branch}" \
                   if r.returncode == 0 else f"FAILED: {r.stderr}"
        
        # === ISSUES ===
        def gh_list_issues(
            repo: str = "nivedjkr/jarvis-assistant",
            state: str = "open",
            limit: int = 10) -> str:
            r = subprocess.run(
                ['gh', 'issue', 'list',
                 '--repo', repo,
                 '--state', state,
                 '--limit', str(limit),
                 '--json', 'number,title,state,createdAt'],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode != 0: return f"FAILED: {r.stderr}"
            issues = json.loads(r.stdout)
            if not issues:
                return f"No {state} issues in {repo}."
            lines = [f"#{i['number']} {i['title']}"
                     for i in issues]
            return f"{len(issues)} issues:\n" + "\n".join(lines)
        
        def gh_create_issue(
            title: str, body: str = "",
            repo: str = "nivedjkr/jarvis-assistant") -> str:
            cmd = ['gh', 'issue', 'create',
                   '--repo', repo, '--title', title]
            if body: cmd += ['--body', body]
            else: cmd += ['--body', '']
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15
            )
            return f"Created: {r.stdout.strip()}" \
                   if r.returncode == 0 else f"FAILED: {r.stderr}"
        
        def gh_close_issue(
            number: int,
            repo: str = "nivedjkr/jarvis-assistant") -> str:
            r = subprocess.run(
                ['gh', 'issue', 'close', str(number),
                 '--repo', repo],
                capture_output=True, text=True, timeout=15
            )
            return f"Closed #{number}" if r.returncode == 0 \
                   else f"FAILED: {r.stderr}"
        
        def gh_comment_issue(
            number: int, comment: str,
            repo: str = "nivedjkr/jarvis-assistant") -> str:
            r = subprocess.run(
                ['gh', 'issue', 'comment', str(number),
                 '--repo', repo, '--body', comment],
                capture_output=True, text=True, timeout=15
            )
            return "Comment added." if r.returncode == 0 \
                   else f"FAILED: {r.stderr}"
        
        # === PULL REQUESTS ===
        def gh_list_prs(
            repo: str = "nivedjkr/jarvis-assistant",
            state: str = "open") -> str:
            r = subprocess.run(
                ['gh', 'pr', 'list',
                 '--repo', repo, '--state', state,
                 '--limit', '10',
                 '--json', 'number,title,state,url'],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode != 0: return f"FAILED: {r.stderr}"
            prs = json.loads(r.stdout)
            if not prs: return "No open PRs."
            lines = [f"#{p['number']} {p['title']}" for p in prs]
            return "\n".join(lines)
        
        def gh_create_pr(
            title: str, body: str = "",
            base: str = "main",
            repo: str = "nivedjkr/jarvis-assistant") -> str:
            cmd = ['gh', 'pr', 'create',
                   '--repo', repo,
                   '--title', title,
                   '--base', base,
                   '--body', body or title]
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            return r.stdout.strip() if r.returncode == 0 \
                   else f"FAILED: {r.stderr}"
        
        def gh_merge_pr(
            number: int,
            repo: str = "nivedjkr/jarvis-assistant") -> str:
            r = subprocess.run(
                ['gh', 'pr', 'merge', str(number),
                 '--repo', repo, '--merge'],
                capture_output=True, text=True, timeout=30
            )
            return f"PR #{number} merged." \
                   if r.returncode == 0 else f"FAILED: {r.stderr}"
        
        # === CI / ACTIONS ===
        def gh_ci_status(
            repo: str = "nivedjkr/jarvis-assistant") -> str:
            r = subprocess.run(
                ['gh', 'run', 'list',
                 '--repo', repo, '--limit', '5',
                 '--json', 'name,status,conclusion,url'],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode != 0: return f"FAILED: {r.stderr}"
            runs = json.loads(r.stdout)
            if not runs: return "No CI runs."
            latest = runs[0]
            c = latest.get('conclusion', 'running')
            icon = '✓' if c == 'success' else '✗'
            return f"CI: {icon} {c.upper()} — {latest['name']}"
        
        def gh_rerun_failed(
            repo: str = "nivedjkr/jarvis-assistant") -> str:
            r = subprocess.run(
                ['gh', 'run', 'list',
                 '--repo', repo, '--limit', '1',
                 '--json', 'databaseId,conclusion'],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode != 0: return f"FAILED: {r.stderr}"
            runs = json.loads(r.stdout)
            if not runs: return "No runs found."
            run_id = runs[0]['databaseId']
            r2 = subprocess.run(
                ['gh', 'run', 'rerun', str(run_id),
                 '--failed', '--repo', repo],
                capture_output=True, text=True, timeout=15
            )
            return "Rerunning failed jobs." \
                   if r2.returncode == 0 else f"FAILED: {r2.stderr}"
        
        # === NOTIFICATIONS ===
        def gh_notifications() -> str:
            r = subprocess.run(
                ['gh', 'api', 'notifications',
                 '--jq', 
                 '.[0:10] | .[] | '
                 '"\(.subject.title) [\(.reason)]"'],
                capture_output=True, text=True, timeout=15
            )
            output = r.stdout.strip()
            return f"Notifications:\n{output}" \
                   if output else "No new notifications."
        
        def gh_mark_notifications_read() -> str:
            r = subprocess.run(
                ['gh', 'api', '--method', 'PUT',
                 'notifications'],
                capture_output=True, text=True, timeout=15
            )
            return "All notifications marked read." \
                   if r.returncode == 0 else f"FAILED: {r.stderr}"
        
        # === GIST ===
        def gh_create_gist(
            filename: str, content: str,
            description: str = "",
            public: bool = False) -> str:
            import tempfile
            # Write to temp file then create gist
            with tempfile.NamedTemporaryFile(
                mode='w', suffix=f'_{filename}',
                delete=False, encoding='utf-8'
            ) as f:
                f.write(content)
                tmp_path = f.name
            
            cmd = ['gh', 'gist', 'create', tmp_path]
            if description: cmd += ['--desc', description]
            if public: cmd += ['--public']
            
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15
            )
            os.unlink(tmp_path)
            return r.stdout.strip() if r.returncode == 0 \
                   else f"FAILED: {r.stderr}"
        
        def gh_list_gists() -> str:
            r = subprocess.run(
                ['gh', 'gist', 'list', '--limit', '10'],
                capture_output=True, text=True, timeout=15
            )
            return r.stdout if r.returncode == 0 \
                   else f"FAILED: {r.stderr}"
        
        # === REGISTER ALL ===
        self._add("git_add_commit_push", 
            git_add_commit_push,
            "Stage all changes, preview diff, and require confirmation before commit and push. "
            "Call when user says push, commit, save to github.",
            {"message": {"type": "string",
                         "description": "Commit message"},
             "path": {"type": "string",
                      "default": "",
                      "description": "Repository path (auto-detected if empty)"},
             "confirmed": {"type": "boolean",
                           "default": False,
                           "description": "Set to true after explicit user confirmation of diff"}},
            required=["message"])
        
        self._add("gh_list_repos", gh_list_repos,
            "List all GitHub repositories for the account.",
            {"limit": {"type": "integer", "default": 20}},
            required=[])
        
        self._add("gh_create_repo", gh_create_repo,
            "Create a new GitHub repository.",
            {"name": {"type": "string"},
             "private": {"type": "boolean", "default": False},
             "description": {"type": "string", "default": ""}},
            required=["name"])
        
        self._add("gh_delete_repo", gh_delete_repo,
            "Delete a GitHub repository.",
            {"repo": {"type": "string"}},
            required=["repo"])
        
        self._add("gh_clone_repo", gh_clone_repo,
            "Clone a GitHub repo to local machine.",
            {"repo": {"type": "string"},
             "path": {"type": "string", "default": "."}},
            required=["repo"])
        
        self._add("gh_repo_info", gh_repo_info,
            "Get info about a specific GitHub repo.",
            {"repo": {"type": "string",
                      "default": "nivedjkr/jarvis-assistant"}},
            required=[])
        
        self._add("git_status", git_status,
            "Check git status of JARVIS project.",
            {"path": {"type": "string",
                      "default": "D:\\JARVIS"}},
            required=[])
        
        self._add("git_pull", git_pull,
            "Pull latest from GitHub.",
            {"path": {"type": "string",
                      "default": "D:\\JARVIS"}},
            required=[])
        
        self._add("git_log", git_log,
            "Show recent commit history.",
            {"limit": {"type": "integer", "default": 10},
             "path": {"type": "string",
                      "default": "D:\\JARVIS"}},
            required=[])
        
        self._add("git_diff", git_diff,
            "Show what files changed since last commit.",
            {"path": {"type": "string",
                      "default": "D:\\JARVIS"}},
            required=[])
        
        self._add("git_create_branch", git_create_branch,
            "Create a new git branch.",
            {"branch": {"type": "string"},
             "path": {"type": "string",
                      "default": "D:\\JARVIS"}},
            required=["branch"])
        
        self._add("git_switch_branch", git_switch_branch,
            "Switch to an existing git branch.",
            {"branch": {"type": "string"},
             "path": {"type": "string",
                      "default": "D:\\JARVIS"}},
            required=["branch"])
        
        self._add("gh_list_issues", gh_list_issues,
            "List GitHub issues.",
            {"repo": {"type": "string",
                      "default": "nivedjkr/jarvis-assistant"},
             "state": {"type": "string", "default": "open"},
             "limit": {"type": "integer", "default": 10}},
            required=[])
        
        self._add("gh_create_issue", gh_create_issue,
            "Create a new GitHub issue.",
            {"title": {"type": "string"},
             "body": {"type": "string", "default": ""},
             "repo": {"type": "string",
                      "default": "nivedjkr/jarvis-assistant"}},
            required=["title"])
        
        self._add("gh_close_issue", gh_close_issue,
            "Close a GitHub issue by number.",
            {"number": {"type": "integer"},
             "repo": {"type": "string",
                      "default": "nivedjkr/jarvis-assistant"}},
            required=["number"])
        
        self._add("gh_comment_issue", gh_comment_issue,
            "Comment on a GitHub issue.",
            {"number": {"type": "integer"},
             "comment": {"type": "string"},
             "repo": {"type": "string",
                      "default": "nivedjkr/jarvis-assistant"}},
            required=["number", "comment"])
        
        self._add("gh_list_prs", gh_list_prs,
            "List pull requests.",
            {"repo": {"type": "string",
                      "default": "nivedjkr/jarvis-assistant"},
             "state": {"type": "string", "default": "open"}},
            required=[])
        
        self._add("gh_create_pr", gh_create_pr,
            "Create a pull request.",
            {"title": {"type": "string"},
             "body": {"type": "string", "default": ""},
             "base": {"type": "string", "default": "main"},
             "repo": {"type": "string",
                      "default": "nivedjkr/jarvis-assistant"}},
            required=["title"])
        
        self._add("gh_merge_pr", gh_merge_pr,
            "Merge a pull request.",
            {"number": {"type": "integer"},
             "repo": {"type": "string",
                      "default": "nivedjkr/jarvis-assistant"}},
            required=["number"])
        
        self._add("gh_ci_status", gh_ci_status,
            "Check CI/Actions status.",
            {"repo": {"type": "string",
                      "default": "nivedjkr/jarvis-assistant"}},
            required=[])
        
        self._add("gh_rerun_failed", gh_rerun_failed,
            "Rerun failed CI jobs.",
            {"repo": {"type": "string",
                      "default": "nivedjkr/jarvis-assistant"}},
            required=[])
        
        self._add("gh_notifications", gh_notifications,
            "Check GitHub notifications.",
            {}, required=[])
        
        self._add("gh_mark_notifications_read",
            gh_mark_notifications_read,
            "Mark all GitHub notifications as read.",
            {}, required=[])
        
        self._add("gh_create_gist", gh_create_gist,
            "Create a GitHub gist from text content.",
            {"filename": {"type": "string"},
             "content": {"type": "string"},
             "description": {"type": "string", "default": ""},
             "public": {"type": "boolean", "default": False}},
            required=["filename", "content"])
        
        self._add("gh_list_gists", gh_list_gists,
            "List your GitHub gists.",
            {}, required=[])

    def _register_system_file_tools(self):
        import shutil
        import glob
        import os
        
        def move_file(src: str, dst: str) -> str:
            try:
                full_src = os.path.abspath(src)
                full_dst = os.path.abspath(dst)
                if not os.path.exists(full_src):
                    return f"FAILED: {src} not found"
                shutil.move(full_src, full_dst)
                return f"Moved: {full_src} → {full_dst}"
            except Exception as e:
                return f"FAILED: {e}"
        
        def copy_file(src: str, dst: str) -> str:
            try:
                full_src = os.path.abspath(src)
                full_dst = os.path.abspath(dst)
                if not os.path.exists(full_src):
                    return f"FAILED: {src} not found"
                if os.path.isdir(full_src):
                    shutil.copytree(full_src, full_dst)
                else:
                    shutil.copy2(full_src, full_dst)
                return f"Copied: {full_src} → {full_dst}"
            except Exception as e:
                return f"FAILED: {e}"
        
        def rename_file(src: str, new_name: str) -> str:
            try:
                full_src = os.path.abspath(src)
                parent = os.path.dirname(full_src)
                full_dst = os.path.join(parent, new_name)
                os.rename(full_src, full_dst)
                return f"Renamed to: {full_dst}"
            except Exception as e:
                return f"FAILED: {e}"
        
        def search_files(
            pattern: str,
            path: str = '.') -> str:
            try:
                full_path = os.path.abspath(path)
                matches = glob.glob(
                    os.path.join(full_path, '**', pattern),
                    recursive=True
                )
                if not matches:
                    return f"No files matching '{pattern}'"
                return f"Found {len(matches)} files:\n" + \
                       "\n".join(matches[:20])
            except Exception as e:
                return f"FAILED: {e}"
        
        def get_file_info(path: str) -> str:
            try:
                full = os.path.abspath(path)
                if not os.path.exists(full):
                    return f"FAILED: {path} not found"
                stat = os.stat(full)
                import datetime
                modified = datetime.datetime.fromtimestamp(
                    stat.st_mtime
                ).strftime('%Y-%m-%d %H:%M:%S')
                size = stat.st_size
                return (f"Path: {full}\n"
                        f"Size: {size:,} bytes\n"
                        f"Modified: {modified}\n"
                        f"Type: {'directory' if os.path.isdir(full) else 'file'}")
            except Exception as e:
                return f"FAILED: {e}"
        
        def append_to_file(path: str, content: str) -> str:
            try:
                full = os.path.abspath(path)
                with open(full, 'a', encoding='utf-8') as f:
                    f.write('\n' + content)
                return f"Appended to: {full}"
            except Exception as e:
                return f"FAILED: {e}"
        
        def find_in_file(
            path: str, search_term: str) -> str:
            try:
                full = os.path.abspath(path)
                if not os.path.exists(full):
                    return f"FAILED: {path} not found"
                with open(full, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                matches = [
                    f"Line {i+1}: {line.rstrip()}"
                    for i, line in enumerate(lines)
                    if search_term.lower() in line.lower()
                ]
                if not matches:
                    return f"'{search_term}' not found in {path}"
                return f"Found {len(matches)} matches:\n" + \
                       "\n".join(matches[:20])
            except Exception as e:
                return f"FAILED: {e}"
        
        def get_disk_usage(path: str = 'C:\\') -> str:
            try:
                usage = shutil.disk_usage(path)
                total_gb = usage.total / (1024**3)
                used_gb = usage.used / (1024**3)
                free_gb = usage.free / (1024**3)
                return (f"Disk {path}:\n"
                        f"Total: {total_gb:.1f} GB\n"
                        f"Used: {used_gb:.1f} GB "
                        f"({usage.used*100//usage.total}%)\n"
                        f"Free: {free_gb:.1f} GB")
            except Exception as e:
                return f"FAILED: {e}"
        
        self._add("move_file", move_file,
            "Move a file or folder to a new location.",
            {"src": {"type": "string"},
             "dst": {"type": "string"}})
        
        self._add("copy_file", copy_file,
            "Copy a file or folder.",
            {"src": {"type": "string"},
             "dst": {"type": "string"}})
        
        self._add("rename_file", rename_file,
            "Rename a file or folder.",
            {"src": {"type": "string"},
             "new_name": {"type": "string"}})
        
        self._add("search_files", search_files,
            "Search for files by name pattern.",
            {"pattern": {"type": "string"},
             "path": {"type": "string", "default": "."}},
            required=["pattern"])
        
        self._add("get_file_info", get_file_info,
            "Get detailed info about a file or folder.",
            {"path": {"type": "string"}})
        
        self._add("append_to_file", append_to_file,
            "Append text to end of a file.",
            {"path": {"type": "string"},
             "content": {"type": "string"}})
        
        self._add("find_in_file", find_in_file,
            "Search for text within a file.",
            {"path": {"type": "string"},
             "search_term": {"type": "string"}})
        
        self._add("get_disk_usage", get_disk_usage,
            "Get real disk space usage.",
            {"path": {"type": "string", "default": "C:\\"}},
            required=[])

    def _register_semantic_memory_tools(self):
        def remember_fact(fact: str, category: str = "") -> str:
            try:
                from jarvis.semantic_memory import SemanticMemory
                mem = SemanticMemory()
                return mem.add_fact(fact, category)
            except Exception as e:
                return f"FAILED: {e}"

        def search_memory(query: str) -> str:
            try:
                from jarvis.semantic_memory import SemanticMemory
                mem = SemanticMemory()
                return str(mem.search(query))
            except Exception as e:
                return f"FAILED: {e}"

        self._add("remember_fact", remember_fact,
            "Store a fact in semantic memory for later recall.",
            {"fact": {"type": "string"},
             "category": {"type": "string", "default": ""}},
            required=["fact"])

        self._add("search_memory", search_memory,
            "Search memory semantically — finds relevant facts "
            "even without exact keyword match.",
            {"query": {"type": "string"}},
            required=["query"])
