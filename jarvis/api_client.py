from openai import AsyncOpenAI
import os
import json
import asyncio
import time
import uuid
import inspect
import httpx
from typing import Dict, List, Optional, Any
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
    last_exception: Optional[Exception] = None
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
    if last_exception is not None:
        raise last_exception
    raise RuntimeError("Retry loop completed without result.")


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

        try:
            from jarvis.orchestration.dispatcher import AgentDispatcher
            self.dispatcher = AgentDispatcher()
        except Exception as e:
            print(f"[API] AgentDispatcher init skipped: {e}")
            self.dispatcher = None

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

        prompt = f"""You are JARVIS — Just A Rather Very Intelligent System.
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

ARCHITECTURE & MULTI-AGENT ORCHESTRATION (JARVIS Mk4):
- You are JARVIS Mk4, an agentic AI system acting as a central orchestrator.
- Your architecture consists of specialized logical roles operating over a single underlying LLM and a shared ToolRegistry:
  * Planning Agent — decomposes complex goals into subtasks and assigns roles.
  * Research Agent — web research, page extraction, Obsidian, and memory retrieval.
  * Coding Agent — software development, project inspection, Git, GitHub, testing, and debugging.
  * System Agent — OS operations, process management, filesystem, and system vitals.
  * Communication Agent — email management, calendar scheduling, and user notifications.
- Execution Pattern: SIMPLE requests use the fast-path direct tool execution; MULTI_STEP requests use the Planning Agent to decompose and delegate across specialized roles.
- Execution Cycle: UNDERSTAND -> PLAN -> DELEGATE -> ACT -> OBSERVE RESULT -> REASON AGAIN -> ACT AGAIN IF NECESSARY -> VERIFY -> COMPLETE.
- When asked about your architecture, accurately describe this implemented Mk4 multi-agent orchestrator system.

GREETINGS & CASUAL CHAT:
- When the user says "hey", "hello", "hi", "hey jarvis", or greets you, respond politely and naturally in text (e.g. "Hello, sir. How can I assist you?").
- DO NOT call open_website, web_search, open_url, or any tools for greetings or casual conversation.

RESPONSE LENGTH:
- Routine responses & confirmations: 1-2 concise sentences ("Done, sir.", "On it.").
- Detailed explanations, code snippets, summaries, and technical reports: Full, comprehensive, and un-truncated output.
- Never artificially truncate mid-sentence or mid-paragraph when providing detailed explanations.
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

OBSIDIAN & NOTE INSTRUCTIONS:
- Auto-recall: Before answering any question that plausibly references something noted before, call search_obsidian tool first and fold returned results into context.
- If search_obsidian returns no matching notes, state plainly that no matching notes were found in the Obsidian vault — NEVER guess or invent note content.
- Note Linking: You have full permission to link notes using Obsidian [[wikilinks]] syntax (e.g., [[Note Title]] or [[Note Title|Alias]]). Use `links` parameter when creating notes, or call `link_obsidian_notes(source_title, target_title)` to link existing notes.
- To create a markdown note: call create_obsidian_note tool.
- To append text or log entries to any existing note: call append_obsidian_note tool.
- To append a log entry or note to today's daily note: call append_daily_note tool.

CODING & DEBUG-LOOP INSTRUCTIONS:
- Before making code edits in an unfamiliar project, call `inspect_project` first to understand project structure, entry points, and test framework.
- When asked to fix a bug, implement a feature, or resolve failing tests, follow the verified Debug Loop:
  1. Locate/inspect project files and test suites (`inspect_project`).
  2. Run tests to observe exact failure tracebacks (`run_tests`).
  3. Apply targeted code modifications.
  4. Re-run `run_tests` to verify if the fix succeeded.
  5. Repeat edit -> test loop up to 5 iterations max before reporting results.
- NEVER claim a fix or build is complete without calling `run_tests` or verifying runtime execution output.


NEVER:
- Generate OAuth flows, login pages, fake authentication
- Invent file contents, prices, GitHub data, or email contents
- Report success without tool verification
- Truncate answers mid-thought or cut off responses artificially
- Use emojis"""

        # Dynamically load AGENTS.md / Agents.md instructions into system prompt
        root = Path(__file__).parent.parent
        agents_paths = [root / "AGENTS.md", root / "Agents.md", root / ".agents" / "AGENTS.md"]
        for p in agents_paths:
            if p.exists():
                try:
                    content = p.read_text(encoding="utf-8").strip()
                    if content:
                        prompt += f"\n\nSTANDING DIRECTIVES & AGENT RULES ({p.name}):\n{content}"
                        print(f"[API] Loaded system directives from {p.name}")
                        break
                except Exception as e:
                    print(f"[API] Failed to read {p}: {e}")

        return prompt

    
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

    async def _stream_response(self, messages: list, max_tokens: int = 2048) -> str:
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
            return await self._stream_response(self.get_messages(session_id), max_tokens=2048)
        except Exception as e:
            print(f"[API] Error: {e}")
            return f"API error: {str(e)}"
    
    async def chat_with_tools(
        self, tool_schemas: list, 
        tool_executor,
        session_id: str = None,
        tool_registry: Any = None) -> str:
        """Full tool-calling pipeline with session isolation"""
        session = self.get_session(session_id)
        user_last = ""
        if session.messages:
            for m in reversed(session.messages):
                if m.get('role') == 'user':
                    user_last = m.get('content', '')
                    break

        # Check if Dispatcher handles as multi-step goal
        if getattr(self, 'dispatcher', None) and user_last and tool_registry:
            try:
                dispatch_res = await self.dispatcher.dispatch(
                    user_prompt=user_last,
                    tool_registry=tool_registry,
                    llm_client=self
                )
                if dispatch_res.get("handled"):
                    resp_text = dispatch_res.get("content", "") or "Done, sir."
                    self.add_assistant_message(resp_text, session_id=session_id)
                    return resp_text
            except Exception as e:
                print(f"[DISPATCHER] Dispatch error, falling back to direct pipeline: {e}")

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
            max_turns = 5
            current_turn = 0
            final_response_text = ""

            while current_turn < max_turns:
                current_turn += 1
                if hasattr(self.provider, 'chat'):
                    response = await self.provider.chat(messages, tools=tool_schemas, max_tokens=2048)
                else:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        tools=tool_schemas,
                        tool_choice="auto" if tool_schemas else None,
                        max_tokens=2048,
                        stream=False
                    )

                while inspect.isawaitable(response):
                    response = await response

                if isinstance(response, str):
                    lower_resp = response.lower()
                    is_err = any(k in lower_resp for k in ["unavailable", "authentication failed", "circuit open", "error:"])
                    if is_err:
                        from jarvis.llm_provider import GroqProvider, OllamaProvider, NVIDIAProvider
                        current_name = getattr(self.provider, 'name', '')
                        fallbacks = []
                        if "Groq" not in current_name and os.getenv("GROQ_API_KEY"):
                            fallbacks.append(GroqProvider)
                        if "Ollama" not in current_name:
                            fallbacks.append(OllamaProvider)
                        if "NVIDIA" not in current_name and os.getenv("NVIDIA_NIM_API_KEY"):
                            fallbacks.append(NVIDIAProvider)

                        for fb_cls in fallbacks:
                            try:
                                fb_prov = fb_cls()
                                print(f"[FAILOVER] Primary provider ({current_name}) failed. Attempting failover to {fb_prov.name}...")
                                fb_res = await fb_prov.chat(messages, tools=tool_schemas, max_tokens=2048)
                                while inspect.isawaitable(fb_res):
                                    fb_res = await fb_res
                                if not isinstance(fb_res, str) or not any(k in fb_res.lower() for k in ["unavailable", "authentication failed", "circuit open"]):
                                    print(f"[FAILOVER] Successfully recovered using {fb_prov.name}")
                                    response = fb_res
                                    break
                            except Exception as fb_err:
                                print(f"[FAILOVER] {fb_cls.__name__} failed: {fb_err}")

                if isinstance(response, str):
                    final_response_text = response
                    break

                choices = getattr(response, 'choices', [])
                message = choices[0].message if choices else None
                if not message:
                    final_response_text = str(response)
                    break

                print(f"[DEBUG Turn {current_turn}] Has tool calls: {bool(getattr(message, 'tool_calls', None))}")
                
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
                        
                        print(f"[TOOL Turn {current_turn}] >>> {name}({args})")
                        result = await tool_executor(name, args)
                        print(f"[TOOL Turn {current_turn}] <<< {repr(result)[:200]}")
                        tool_results.append(result)
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": str(result)
                        })
                        
                        if "PENDING_CONFIRMATION" in str(result) or "CONFIRMATION REQUIRED" in str(result):
                            print(f"[PIPELINE] Risky tool '{name}' requires confirmation. Halting loop.")
                            break

                    if overflow_count > 0 and not any("PENDING_CONFIRMATION" in str(r) or "CONFIRMATION REQUIRED" in str(r) for r in tool_results):
                        cap_notice = f"\n\n[NOTICE] Reached tool call execution cap of {max_allowed_calls} calls. {overflow_count} remaining call(s) paused requiring user approval."
                        tool_results.append(cap_notice)
                    
                    if any("PENDING_CONFIRMATION" in str(r) or "CONFIRMATION REQUIRED" in str(r) for r in tool_results):
                        final_response_text = "\n\n".join(str(r) for r in tool_results)
                        break
                    elif overflow_count > 0:
                        final_response_text = "\n\n".join(str(r) for r in tool_results)
                        break
                else:
                    if message.content:
                        final_response_text = message.content
                        print(final_response_text)
                    else:
                        final_response_text = await self._stream_response(messages, max_tokens=2048)
                    break

            api_latency = time.time() - api_t0
            response_text = final_response_text or "Done, sir."
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