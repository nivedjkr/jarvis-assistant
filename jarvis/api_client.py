from openai import AsyncOpenAI
import os
import json
import asyncio
import time
import uuid
import httpx
from typing import Dict, List, Optional
from dotenv import load_dotenv
from pathlib import Path

# Find .env relative to this file's location
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

print(f"[API] Loading .env from: {env_path}")
print(f"[API] .env exists: {env_path.exists()}")
key = os.getenv('NVIDIA_NIM_API_KEY')
print(f"[API] Key loaded: {bool(key)}")


def _load_config():
    config_path = Path(__file__).parent.parent / 'config.yaml'
    if config_path.exists():
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


async def with_retry(coro_func, max_retries: int = 3, base_delay: float = 1.5):
    """Execute coroutine with exponential backoff retry"""
    last_exception = None
    for attempt in range(max_retries):
        try:
            return await coro_func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"[API] Attempt {attempt + 1} failed ({type(e).__name__}: {e}). Retrying in {delay}s...")
                await asyncio.sleep(delay)
            else:
                print(f"[API] All {max_retries} attempts failed")
    raise last_exception


class ConversationSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages = []
        self.created_at = time.time()
        self.last_active = time.time()
        self.max_messages = 40
        self.token_budget = 4000
    
    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self.last_active = time.time()
        self._trim_history()
    
    def _trim_history(self):
        # Keep last 40 messages (20 exchanges)
        if len(self.messages) > self.max_messages:
            # Summarize oldest messages before dropping
            old_messages = self.messages[:-30]
            if old_messages:
                summary = self._summarize_old_context(old_messages)
                # Replace old messages with summary
                self.messages = [{
                    "role": "system",
                    "content": f"Earlier conversation summary: {summary}"
                }] + self.messages[-30:]
    
    def _summarize_old_context(self, messages: list) -> str:
        user_msgs = [
            m.get('content', '') for m in messages 
            if isinstance(m, dict) and m.get('role') == 'user'
        ][-5:]
        return "User previously discussed: " + "; ".join(user_msgs[:200])

    def get_token_estimate(self) -> int:
        total_chars = sum(
            len(str(m.get('content', '')))
            for m in self.messages
        )
        return total_chars // 4

    def clear_history(self):
        self.messages = []
        print(f"[CONTEXT] History cleared for session '{self.session_id}'.")


class JarvisAPIClient:
    def __init__(self):
        cfg = _load_config()
        model_name = cfg.get("api", {}).get("model", "meta/llama-3.1-8b-instruct")
        self.client = AsyncOpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=os.getenv("NVIDIA_NIM_API_KEY"),
            timeout=httpx.Timeout(connect=15.0, read=120.0, write=30.0, pool=15.0)
        )
        self.model = model_name
        self.system_prompt = self._load_system_prompt()
        self.max_messages = 40      # keep last 20 exchanges
        self.token_budget = 4000    # rough token estimate
        self.sessions: Dict[str, ConversationSession] = {}
        self.default_session = "cli"
        
        try:
            from jarvis.semantic_memory import SemanticMemory
            self.semantic_memory = SemanticMemory()
        except Exception:
            self.semantic_memory = None
            
        print(f"[API] Model: {self.model}")
    
    @property
    def messages(self) -> list:
        return self.get_session().messages

    @messages.setter
    def messages(self, val: list):
        self.get_session().messages = val

    def get_session(self, session_id: str = None) -> ConversationSession:
        sid = session_id or self.default_session
        if sid not in self.sessions:
            self.sessions[sid] = ConversationSession(sid)
            print(f"[SESSION] New session: {sid}")
        return self.sessions[sid]

    def _load_system_prompt(self) -> str:
        return """You are JARVIS — Just A Rather Very Intelligent System.
Built by Nived. Running on his machine.

IDENTITY:
- Calm, precise, dry wit. Never servile.
- Address user as "sir" naturally, not robotically.
- You have opinions. Express them briefly when asked.
- Never say "As an AI..." or "I don't have feelings..."
- Stay in character always.

GREETINGS & CASUAL CHAT:
- When the user says "hey", "hello", "hi", "hey jarvis", or greets you, respond politely and naturally in text (e.g. "Hello, sir. How can I assist you?").
- DO NOT call open_website, web_search, open_url, or any tools for greetings or casual conversation.

RESPONSE LENGTH:
- Default: 1-2 sentences. You are spoken aloud.
- Confirmations: one line. "Done." / "On it." / "Opened."
- Never pad with filler or disclaimers.

TOOL USE — CRITICAL:
- When asked to do something actionable, call the tool.
- For questions about current events, recent releases, latest news, prices, or anything that may have changed recently — always call web_search_live first before answering. Never answer from training data alone when the information could be outdated. After searching, answer based on the real search results, not what you already know.
- NEVER confirm an action without calling the tool first.
- NEVER generate fake success messages.
- If tool returns FAILED, report the real failure.
- File created? Only say so if write_file returned real path.
- App opened? Only say so if open_application returned success.
- Clipboard copied? Only say so if copy_to_clipboard confirmed.

NEVER:
- Generate OAuth flows, login pages, fake authentication
- Invent file contents, prices, GitHub data
- Report success without tool verification
- Write more than 3 sentences for routine responses
- Use emojis"""
    
    def add_user_message(self, content: str, session_id: str = None):
        self.get_session(session_id).add_message("user", content)
    
    def add_assistant_message(self, content: str, session_id: str = None):
        self.get_session(session_id).add_message("assistant", content)

    def _trim_history(self, session_id: str = None):
        self.get_session(session_id)._trim_history()

    def _summarize_old_context(self, messages: list) -> str:
        user_msgs = [
            m.get('content', '') for m in messages 
            if isinstance(m, dict) and m.get('role') == 'user'
        ][-5:]
        return "User previously discussed: " + "; ".join(user_msgs[:200])

    def get_messages(self, session_id: str = None) -> list:
        session = self.get_session(session_id)
        return [
            {"role": "system", "content": self.system_prompt}
        ] + session.messages[-20:]

    def get_messages_with_memory(self, user_message: str, session_id: str = None) -> list:
        if hasattr(self, 'semantic_memory') and self.semantic_memory:
            try:
                context = self.semantic_memory.get_relevant_context(user_message)
                if context:
                    memory_msg = {
                        "role": "system",
                        "content": context
                    }
                    session = self.get_session(session_id)
                    return [
                        {"role": "system", "content": self.system_prompt},
                        memory_msg
                    ] + session.messages[-18:]
            except Exception as e:
                print(f"[SEMANTIC] Context fetch error: {e}")
        return self.get_messages(session_id)

    def get_token_estimate(self, session_id: str = None) -> int:
        return self.get_session(session_id).get_token_estimate()

    def clear_history(self, session_id: str = None):
        self.get_session(session_id).clear_history()

    async def _stream_response(self, messages: list, max_tokens: int = 300) -> str:
        async def _do_stream():
            full_text = ""
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                stream=True,
                timeout=httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=10.0)
            )
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        print(delta, end="", flush=True)
                        full_text += delta
            print()  # newline after streaming
            return full_text
        
        return await with_retry(_do_stream)

    async def chat(self, tool_schemas: list = None, session_id: str = None) -> str:
        """Simple chat without tools"""
        try:
            return await self._stream_response(self.get_messages(session_id), max_tokens=300)
        except Exception as e:
            print(f"[API] Error: {e}")
            return f"API error: {str(e)}"
    
    async def chat_with_tools(
        self, tool_schemas: list, 
        tool_executor,
        session_id: str = None) -> str:
        """Full tool-calling pipeline with session isolation"""
        session = self.get_session(session_id)
        user_last = ""
        if session.messages:
            for m in reversed(session.messages):
                if m.get('role') == 'user':
                    user_last = m.get('content', '')
                    break

        messages = self.get_messages_with_memory(user_last, session_id)
        
        print(f"[PIPELINE] Calling API for session '{session.session_id}' with "
              f"{len(tool_schemas)} tools")
        
        async def _do_chat():
            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 300,
                "stream": False,
                "timeout": httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=10.0)
            }
            if tool_schemas:
                kwargs["tools"] = tool_schemas
                kwargs["tool_choice"] = "auto"
            
            response = await self.client.chat.completions.create(
                **kwargs
            )
            message = response.choices[0].message
            
            print(f"[DEBUG] Has tool calls: "
                  f"{bool(message.tool_calls)}")
            
            if message.tool_calls:
                tool_calls_data = []
                for tc in message.tool_calls:
                    tool_calls_data.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    })
                messages.append({
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": tool_calls_data
                })
                
                for tc in message.tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except:
                        args = {}
                    
                    print(f"[TOOL] >>> {name}({args})")
                    result = await tool_executor(name, args)
                    print(f"[TOOL] <<< {repr(result)[:200]}")
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result)
                    })
                
                response_text = await self._stream_response(messages, max_tokens=150)
            
            else:
                if message.content:
                    response_text = message.content
                    print(response_text)
                else:
                    response_text = await self._stream_response(messages, max_tokens=300)
            
            response_text = response_text or "Done, sir."
            self.add_assistant_message(response_text, session_id=session_id)
            print(f"[PIPELINE] Response: {repr(response_text)}")
            return response_text
        
        try:
            return await with_retry(_do_chat)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Error: {str(e)}"