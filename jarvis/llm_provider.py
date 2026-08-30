from abc import ABC, abstractmethod
from openai import AsyncOpenAI
import os
import inspect
import httpx
from typing import List, Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

# Ensure .env loaded
load_dotenv(Path(__file__).parent.parent / '.env')

from jarvis.config_manager import config
from jarvis.error_recovery import recovery

_SHARED_HTTP_CLIENT: Optional[httpx.AsyncClient] = None


def get_shared_http_client() -> httpx.AsyncClient:
    global _SHARED_HTTP_CLIENT
    if _SHARED_HTTP_CLIENT is None or _SHARED_HTTP_CLIENT.is_closed:
        _SHARED_HTTP_CLIENT = httpx.AsyncClient(
            limits=httpx.Limits(max_keepalive_connections=30, max_connections=100, keepalive_expiry=300.0),
            timeout=httpx.Timeout(45.0, connect=10.0)
        )
    return _SHARED_HTTP_CLIENT


class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self, messages: list,
        tools: Optional[list] = None,
        max_tokens: int = 2048) -> Any:
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass

class NVIDIAProvider(LLMProvider):
    def __init__(self):
        model_name = config.get("api.model", "nvidia/nemotron-3-ultra-550b-a55b")
        base_url = config.get("api.base_url", "https://integrate.api.nvidia.com/v1")
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=os.getenv("NVIDIA_NIM_API_KEY") or "mock_key",
            http_client=get_shared_http_client()
        )
        self.model = model_name

    @property
    def name(self) -> str:
        return "NVIDIA NIM"

    async def chat(self, messages: list, tools: Optional[list] = None, max_tokens: int = 2048) -> Any:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": False,
            "timeout": 45.0
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        res = await recovery.call_with_recovery(
            self.name,
            self.client.chat.completions.create,
            "NVIDIA NIM API temporarily unavailable, sir.",
            **kwargs
        )
        while inspect.isawaitable(res):
            res = await res
        return res

class GroqProvider(LLMProvider):
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY") or "mock_key",
            http_client=get_shared_http_client()
        )
        self.model = "llama-3.3-70b-versatile"

    @property
    def name(self) -> str:
        return "Groq"

    async def chat(self, messages: list, tools: Optional[list] = None, max_tokens: int = 2048) -> Any:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "timeout": 45.0
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        res = await recovery.call_with_recovery(
            self.name,
            self.client.chat.completions.create,
            "Groq API temporarily unavailable, sir.",
            **kwargs
        )
        while inspect.isawaitable(res):
            res = await res
        return res

class AnthropicProvider(LLMProvider):
    def __init__(self):
        try:
            import importlib
            anthropic = importlib.import_module("anthropic")
            self.client = anthropic.AsyncAnthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY") or "mock_key",
                timeout=45.0
            )
        except (ImportError, Exception):
            self.client = None
        self.model = "claude-sonnet-4-6"

    @property
    def name(self) -> str:
        return "Anthropic Claude"

    async def chat(self, messages: list, tools: Optional[list] = None, max_tokens: int = 2048) -> Any:
        if not self.client:
            raise RuntimeError("anthropic SDK is not installed.")

        system = next(
            (m['content'] for m in messages 
             if isinstance(m, dict) and m.get('role') == 'system'), "")
        msgs = [m for m in messages 
                if isinstance(m, dict) and m.get('role') != 'system']
        
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": msgs,
            "timeout": 45.0
        }

        res = await recovery.call_with_recovery(
            self.name,
            self.client.messages.create,
            "Anthropic API temporarily unavailable, sir.",
            **kwargs
        )
        while inspect.isawaitable(res):
            res = await res
        return res

class OllamaProvider(LLMProvider):
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            http_client=get_shared_http_client()
        )
        self.model = "llama3.2"

    @property
    def name(self) -> str:
        return "Ollama (local)"

    async def chat(self, messages: list, tools: Optional[list] = None, max_tokens: int = 2048) -> Any:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "timeout": 45.0
        }
        if tools:
            kwargs["tools"] = tools

        res = await recovery.call_with_recovery(
            self.name,
            self.client.chat.completions.create,
            "Local Ollama service unavailable, sir.",
            **kwargs
        )
        while inspect.isawaitable(res):
            res = await res
        return res

class GeminiProvider(LLMProvider):
    def __init__(self):
        model_name = config.get("api.gemini_model", "gemini-2.0-flash")
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "mock_key"
        self.client = AsyncOpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=api_key,
            http_client=get_shared_http_client()
        )
        self.model = model_name

    @property
    def name(self) -> str:
        return "Google Gemini"

    async def chat(self, messages: list, tools: Optional[list] = None, max_tokens: int = 2048) -> Any:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": False,
            "timeout": 45.0
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        res = await recovery.call_with_recovery(
            self.name,
            self.client.chat.completions.create,
            "Google Gemini API temporarily unavailable, sir.",
            **kwargs
        )
        while inspect.isawaitable(res):
            res = await res
        return res

def get_provider(name: Optional[str] = None) -> LLMProvider:
    providers = {
        "nvidia": NVIDIAProvider,
        "groq": GroqProvider,
        "gemini": GeminiProvider,
        "anthropic": AnthropicProvider,
        "ollama": OllamaProvider
    }
    provider_name = name or os.getenv("JARVIS_LLM_PROVIDER") or config.get("api.provider", "nvidia")
    cls = providers.get(str(provider_name).lower())
    if not cls:
        print(f"[LLM] Unknown provider: {provider_name}, falling back to NVIDIA")
        cls = NVIDIAProvider
    provider = cls()
    recovery.reset_circuit(provider.name)
    print(f"[LLM] Using provider: {provider.name}")
    return provider

