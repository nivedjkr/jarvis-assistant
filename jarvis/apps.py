"""
App Registry for JARVIS PC Control
Manages application mapping, fuzzy matching, and persistent storage in jarvis/data/apps.json
"""

import json
import os
import difflib
from typing import Dict, List, Tuple, Optional
from pathlib import Path


DEFAULT_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "chrome": "chrome.exe",
    "vscode": "code",
    "vs code": "code",
    "code": "code",
    "visual studio code": "code",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "settings": "start ms-settings:",
    "edge": "msedge.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe"
}


class AppRegistry:
    """Manages mapped application launchers with persistent JSON storage"""

    def __init__(self, json_path: str = "jarvis/data/apps.json"):
        self.json_path = json_path
        path = Path(json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.apps = self.load_apps()

    def load_apps(self) -> Dict[str, str]:
        """Load apps dictionary from JSON file or initialize default"""
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except (json.JSONDecodeError, IOError):
                pass

        # Write default apps if missing or invalid
        self.save_apps_data(DEFAULT_APPS)
        return DEFAULT_APPS.copy()

    def save_apps_data(self, data: Dict[str, str]):
        """Save dictionary to JSON file"""
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def save(self):
        """Save current apps state to disk"""
        self.save_apps_data(self.apps)

    def resolve_app(self, name: str) -> Tuple[Optional[str], List[str], Optional[str]]:
        """
        Resolve application name to launcher command.
        Returns tuple: (resolved_command, fuzzy_matches_list, matched_app_name_if_fuzzy)
        """
        name_clean = name.strip().lower()
        
        # 1. Exact match
        if name_clean in self.apps:
            return self.apps[name_clean], [], None

        # 2. Substring match
        substring_matches = [k for k in self.apps.keys() if name_clean in k or k in name_clean]
        if len(substring_matches) == 1:
            matched_key = substring_matches[0]
            return self.apps[matched_key], [], matched_key

        # 3. Fuzzy match using difflib
        matches = difflib.get_close_matches(name_clean, self.apps.keys(), n=3, cutoff=0.55)
        if len(matches) == 1:
            matched_key = matches[0]
            return self.apps[matched_key], [], matched_key
        elif len(matches) > 1:
            return None, matches, None

        return None, [], None

    def add_app(self, name: str, command: str) -> bool:
        """Add or update an app mapping"""
        name_clean = name.strip().lower()
        if not name_clean or not command.strip():
            return False
        
        self.apps[name_clean] = command.strip()
        self.save()
        return True

    def remove_app(self, name: str) -> bool:
        """Remove an app mapping"""
        name_clean = name.strip().lower()
        if name_clean in self.apps:
            del self.apps[name_clean]
            self.save()
            return True
        return False

    def list_apps(self) -> Dict[str, str]:
        """Return dict of registered apps"""
        return self.apps.copy()
