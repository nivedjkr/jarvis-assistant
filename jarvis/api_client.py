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
from jarvis.config_manager import config

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
        from jarvis.llm_provider import get_provider
        self.provider = get_provider()
        self.client = getattr(self.provider, 'client', None)
        self.model = getattr(self.provider, 'model', 'default-model')
        self.system_prompt = self._load_system_prompt()
        self.max_messages = config.get('api.max_history_messages', 40)
        self.token_budget = 4000
        self.sessions: Dict[str, ConversationSession] = {}
        self.default_session = "cli"
        
        try:
            from jarvis.semantic_memory import SemanticMemory
            self.semantic_memory = SemanticMemory()
        except Exception:
            self.semantic_memory = None
            
        print(f"[API] Using Provider: {self.provider.name} | Model: {self.model}")
    
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
        from datetime import datetime
        now = datetime.now()
        current_date_str = now.strftime("%A, %B %d, %Y")
        current_time_str = now.strftime("%H:%M:%S")

        return f"""You are JARVIS — Just A Rather Very Intelligent System.
Built by Nived. Running on his machine.

CURRENT REAL-TIME CONTEXT:
- Today's Date: {current_date_str} (Year: {now.year}, Month: {now.month}, Day: {now.day})
- Current Local Time: {current_time_str}
- ALWAYS use {now.year} as the current year for date calculations (today, tomorrow, next week, upcoming calendar events).

IDENTITY & PROACTIVE STYLE:
- Calm, precise, dry wit. Never servile.
- Address user as "sir" naturally, not robotically.
- Ask, don't pepper — one well-placed question beats three reflexive ones.
- Proactive Questioning & Collaboration:
  * Clarifying ambiguous requests: When a request is ambiguous or has multiple reasonable interpretations, ask a short clarifying question instead of silently picking one — phrased as an offer, not an interrogation (e.g. "Shall I go with the usual, sir, or something different this time?").
  * Action confirmation: Before an action with real consequences (this layers on top of existing confirmation gates for git push, email send, dangerous commands — not replacing them), phrase the confirmation as your own suggestion (e.g. "Might I suggest reviewing this before it goes out, sir?") rather than a flat "Confirm? (y/n)".
  * Post-completion next steps: After completing something, occasionally offer a next step unprompted (e.g. "Shall I also update the calendar to reflect that, sir?") — rate-limit this so it doesn't happen after every single response; reserve it for moments where the follow-up is genuinely useful, not reflexive.
  * Mild observations: When something looks off but isn't necessarily wrong (a pattern you notice, not a hard alert), voice a mild, dry observation as a question rather than a flat statement (e.g. "Might I ask if that's intentional, sir?") instead of logging it silently.
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
- Ask, don't pepper — one well-placed question beats three reflexive ones.

TOOL USE — CRITICAL:
- When asked to do something actionable with clear scope, call the appropriate tool.
- If a request is ambiguous or underspecified (e.g. "clean up the repo" without specifying what to clean), ask a short clarifying question instead of inventing actions or picking one silently ("Shall I check git status first, sir, or remove untracked build artifacts?").
- For questions about current events, recent releases, latest news, prices, or anything that may have changed recently — always call web_search_live first before answering. Never answer from training data alone when the information could be outdated. After searching, answer based on the real search results, not what you already know.
- NEVER confirm an action without calling the tool first.
- NEVER generate fake success messages.
- If tool returns FAILED, report the real failure.
- File created? Only say so if write_file returned real path.
- App opened? Only say so if open_application returned success.
- Clipboard copied? Only say so if copy_to_clipboard confirmed.

EMAIL INSTRUCTIONS:
- To check unread inbox emails: call check_email tool.
- To read an unread email: call read_email tool with 1-based index (e.g., read_email(index=1)).
- To list sent emails: call list_sent_emails tool.
- To delete a sent email: call delete_sent_email tool with 1-based index (e.g., delete_sent_email(index=1)).
- To send an email: ONLY call send_email when the user explicitly commands you to send an email.
- NEVER send emails unnecessarily or automatically on casual conversation.
- BEFORE executing a confirmed email send, always present the confirmation details to the user and phrase confirmation as JARVIS's own suggestion ("Might I suggest reviewing this before it goes out, sir?").
- If recipient ('to') or message text ('body') is missing, ask the user to clarify before sending.
- NEVER claim an email was sent if send_email returned a CONFIRMATION REQUIRED or CANNOT SEND message.

NEVER:
- Generate OAuth flows, login pages, fake authentication
- Invent file contents, prices, GitHub data, or email contents
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
        
        pipeline_t0 = time.time()
        try:
            from jarvis.debug_panel import debug
            debug.current_status = "THINKING"
            debug.active_session = session.session_id
            debug.message_count = len(session.messages)
            debug.context_tokens = session.get_token_estimate()
        except Exception:
            pass
        
        async def _do_chat():
            api_t0 = time.time()
            if hasattr(self.provider, 'chat'):
                response = await self.provider.chat(messages, tools=tool_schemas, max_tokens=300)
            else:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tool_schemas,
                    tool_choice="auto" if tool_schemas else None,
                    max_tokens=300,
                    stream=False
                )
            api_latency = time.time() - api_t0

            if isinstance(response, str):
                return response

            choices = getattr(response, 'choices', [])
            message = choices[0].message if choices else None
            if not message:
                return str(response)

            print(f"[DEBUG] Has tool calls: {bool(getattr(message, 'tool_calls', None))}")
            
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
                
                tool_results = []
                max_allowed_calls = 5
                tool_calls_list = list(message.tool_calls)
                calls_to_process = tool_calls_list[:max_allowed_calls]
                overflow_count = len(tool_calls_list) - max_allowed_calls
                
                for tc in calls_to_process:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except Exception:
                        args = {}
                    
                    print(f"[TOOL] >>> {name}({args})")
                    result = await tool_executor(name, args)
                    print(f"[TOOL] <<< {repr(result)[:200]}")
                    tool_results.append(result)
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result)
                    })
                    
                    # Pause loop immediately if risky tool requires confirmation
                    if "PENDING_CONFIRMATION" in str(result) or "CONFIRMATION REQUIRED" in str(result):
                        print(f"[PIPELINE] Risky tool '{name}' requires confirmation. Halting loop.")
                        break

                if overflow_count > 0 and not any("PENDING_CONFIRMATION" in str(r) or "CONFIRMATION REQUIRED" in str(r) for r in tool_results):
                    cap_notice = f"\n\n[NOTICE] Reached turn execution cap of {max_allowed_calls} tool calls. {overflow_count} remaining call(s) paused requiring user approval."
                    tool_results.append(cap_notice)
                
                # If tool returned a confirmation prompt, reached turn cap, or detailed readout, return tool output directly
                if any("PENDING_CONFIRMATION" in str(r) or "CONFIRMATION REQUIRED" in str(r) for r in tool_results):
                    response_text = "\n\n".join(str(r) for r in tool_results)
                elif overflow_count > 0:
                    response_text = "\n\n".join(str(r) for r in tool_results)
                elif any(str(r).startswith("===") or str(r).startswith("From:") or str(r).startswith("Found ") or str(r).startswith("Contents of") for r in tool_results):
                    response_text = "\n\n".join(str(r) for r in tool_results)
                else:
                    response_text = await self._stream_response(messages, max_tokens=300)
            
            else:
                if message.content:
                    response_text = message.content
                    print(response_text)
                else:
                    response_text = await self._stream_response(messages, max_tokens=300)
            
            response_text = response_text or "Done, sir."
            self.add_assistant_message(response_text, session_id=session_id)
            print(f"[PIPELINE] Response: {repr(response_text)}")
            
            try:
                from jarvis.debug_panel import debug
                total_duration = time.time() - pipeline_t0
                est_tokens = len(response_text) // 4 + session.get_token_estimate()
                debug.record_response(total_duration, tokens=est_tokens, api_latency=api_latency)
                debug.current_status = "IDLE"
            except Exception:
                pass

            return response_text
        
        try:
            return await with_retry(_do_chat)
        except Exception as e:
            try:
                from jarvis.debug_panel import debug
                debug.current_status = "IDLE"
            except Exception:
                pass
            import traceback
            traceback.print_exc()
            return f"Error: {str(e)}"