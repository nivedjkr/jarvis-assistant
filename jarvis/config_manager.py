import yaml
import os
from pathlib import Path
from typing import Any, Dict, Optional

class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self):
        if getattr(self, '_loaded', False):
            return
        self.config: Dict[str, Any] = {}
        self._load()
        self._loaded = True

    def _load(self):
        config_path = Path('config.yaml')
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"[CONFIG] Warning loading config.yaml: {e}")
                self.config = {}
        else:
            self.config = {}
            
        # Override with env vars
        self._apply_env_overrides()
        print(f"[CONFIG] Loaded {len(self.config)} top-level settings")

    def _apply_env_overrides(self):
        env_map = {
            "NVIDIA_NIM_API_KEY": "api.nvidia_key",
            "JARVIS_LLM_PROVIDER": "api.provider",
            "OPENWEATHER_API_KEY": "weather.api_key",
            "PICOVOICE_ACCESS_KEY": "voice.picovoice_key",
            "JARVIS_USER_TITLE": "personality.user_title",
        }
        for env_var, config_path in env_map.items():
            value = os.getenv(env_var)
            if value:
                self.set(config_path, value)

    def get(self, path: str, default: Any = None) -> Any:
        keys = path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, path: str, value: Any):
        keys = path.split('.')
        d = self.config
        for key in keys[:-1]:
            if key not in d or not isinstance(d[key], dict):
                d[key] = {}
            d = d[key]
        d[keys[-1]] = value

    def reload(self):
        self.config = {}
        self._load()

    def save(self):
        with open('config.yaml', 'w', encoding='utf-8') as f:
            yaml.dump(self.config, f, default_flow_style=False)
        print("[CONFIG] Saved.")

    def get_all(self) -> dict:
        return self.config

# Global instance
config = ConfigManager()
