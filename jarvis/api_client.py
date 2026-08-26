from openai import AsyncOpenAI
import os
import json
import asyncio
import time
import uuid
import inspect
import httpx
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from pathlib import Path
from jarvis.config_manager import config
from jarvis.tool_normalizer import (
    normalize_tool_calls, classify_response, is_unresolved_tool_call, ResponseClassification
)


@dataclass
class AgentResult:
    final_answer: str
    status: str = "COMPLETE"  # "COMPLETE" | "PARTIAL_COMPLETE" | "FAILED" | "TIMEOUT"
    tool_count: int = 0
    iterations: int = 0
    execution_trace: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "final_answer": self.final_answer,
            "status": self.status,
            "tool_count": self.tool_count,
            "iterations": self.iterations,
            "execution_trace": self.execution_trace
        }


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
    def __init__(self, session_id: str, title: str = "New Conversation", created_at: Optional[float] = None, last_active: Optional[float] = None, db_path: Optional[str] = None):
        self.session_id = session_id
        self.title = title
        self.created_at = created_at or time.time()
        self.last_active = last_active or time.time()
        self.db_path = db_path
        self.max_messages = 40
        self.token_budget = 4000
        self.messages: List[Dict[str, Any]] = []
        self._load_from_db()
    
    def _load_from_db(self):
        try:
            from jarvis.memory import Memory
            mem = Memory(db_path=self.db_path) if self.db_path else Memory()
            s_info = mem.get_session(self.session_id)
            if s_info:
                if s_info.get("title"):
                    self.title = s_info["title"]
                if s_info.get("created_at"):
                    self.created_at = s_info["created_at"]
                if s_info.get("last_active"):
                    self.last_active = s_info["last_active"]
            db_msgs = mem.get_session_messages(self.session_id, limit=self.max_messages)
            if db_msgs:
                self.messages = [{"role": m["role"], "content": m["content"]} for m in db_msgs]
        except Exception as e:
            print(f"[SESSION] DB load error for '{self.session_id}': {e}")

    def add_message(self, role: str, content: str):
        now = time.time()
        self.messages.append({"role": role, "content": content})
        self.last_active = now
        
        # Auto-generate title from first user message if default
        if self.title in ("New Conversation", "cli", "") and role == "user":
            clean_title = content.strip().replace("\n", " ")
            if len(clean_title) > 35:
                clean_title = clean_title[:32] + "..."
            if clean_title:
                self.title = clean_title
        
        # Write message directly to SQLite database
        try:
            from jarvis.memory import Memory
            mem = Memory(db_path=self.db_path) if self.db_path else Memory()
            mem.save_session(self.session_id, title=self.title, created_at=self.created_at, last_active=self.last_active)
            mem.add_session_message(self.session_id, role, content, timestamp=now)
        except Exception as e:
            print(f"[SESSION] DB write error for '{self.session_id}': {e}")

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
        try:
            from jarvis.memory import Memory
            mem = Memory()
            mem.clear_session_messages(self.session_id)
        except Exception as e:
            print(f"[SESSION] DB clear error: {e}")
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
        self._load_sessions_from_db()
        
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
    
    def _load_sessions_from_db(self):
        try:
            from jarvis.memory import Memory
            mem = Memory()
            db_sessions = mem.list_sessions()
            for s in db_sessions:
                sid = s["session_id"]
                self.sessions[sid] = ConversationSession(
                    session_id=sid,
                    title=s.get("title", "New Conversation"),
                    created_at=s.get("created_at"),
                    last_active=s.get("last_active")
                )
            print(f"[SESSION] Loaded {len(self.sessions)} sessions from database.")
        except Exception as e:
            print(f"[SESSION] Error loading sessions from DB: {e}")

    def list_sessions(self) -> List[Dict[str, Any]]:
        try:
            from jarvis.memory import Memory
            mem = Memory()
            return mem.list_sessions()
        except Exception:
            return [
                {
                    "session_id": s.session_id,
                    "title": s.title,
                    "created_at": s.created_at,
                    "last_active": s.last_active,
                    "message_count": len(s.messages)
                }
                for s in self.sessions.values()
            ]

    def new_session(self, session_id: Optional[str] = None, title: str = "New Conversation") -> ConversationSession:
        sid = session_id or f"session_{uuid.uuid4().hex[:8]}"
        sess = ConversationSession(sid, title=title)
        self.sessions[sid] = sess
        try:
            from jarvis.memory import Memory
            mem = Memory()
            mem.save_session(sid, title=title, created_at=sess.created_at, last_active=sess.last_active)
        except Exception as e:
            print(f"[SESSION] Error saving new session to DB: {e}")
        return sess

    def switch_session(self, session_id: str) -> ConversationSession:
        return self.get_session(session_id)

    def rename_session(self, session_id: str, title: str) -> bool:
        sess = self.get_session(session_id)
        sess.title = title
        try:
            from jarvis.memory import Memory
            mem = Memory()
            return mem.rename_session(session_id, title)
        except Exception:
            return False

    def delete_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
        try:
            from jarvis.memory import Memory
            mem = Memory()
            return mem.delete_session(session_id)
        except Exception:
            return False

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

HEADLESS BROWSING INSTRUCTIONS:
- Prefer web_search_live or get_webpage_content for simple search queries and static web pages.
- ONLY reach for browse_page or browse_click when the target page requires JavaScript rendering (single-page applications, dynamic DOM) or multi-step navigation. Do not default to browse_page for simple queries.
- Use browse_screenshot to capture a visual rendering of the active browser page when requested.
- Use browse_extract_links to harvest page hyperlinks and navigation structure.
- Call browse_close to explicitly release browser resources after completing multi-step web interaction.

PROACTIVE OBSIDIAN MEMORY FILING INSTRUCTIONS:
- Evaluate whether the user's message contains a durable fact worth remembering — a stated preference, a decision, a recurring topic, or a fact about a person or project — as distinct from small talk or a throwaway question (e.g. "what's 2+2" or "hello").
- If a durable fact is present:
  1. ALWAYS call search_obsidian first to check whether a relevant memory note already exists in the vault.
  2. If a relevant note exists, append/extend it using append_obsidian_note.
  3. If no relevant note exists, create one using create_obsidian_note in the appropriate subfolder structure under Memory/:
     - Memory/profile.md for personal preferences, user identity, and user habits (one file for profile facts).
     - Memory/topics/<topic>.md for topic-specific facts, technical decisions, and reference info.
     - Memory/people/<name>.md for facts about specific individuals.
     - Memory/areas/<project>.md for facts about projects or areas of responsibility.
- JUDGMENT RULES:
  * Don't file the same fact twice: do not create a new note or append duplicate text for something already captured.
  * Don't log passwords, API keys, tokens, or confidential credentials mentioned in passing.
  * Always prefer updating an existing file in Memory/ over creating near-duplicate files.
  * Do NOT log transient or throwaway queries (e.g., math calculations like "what's 2+2", greetings, casual chit-chat, simple web searches).`

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

    async def _stream_response(self, messages: list, max_tokens: int = 2048, chunk_callback=None) -> str:
        async def _do_stream():
            full_text = ""
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                stream=True,
                timeout=httpx.Timeout(connect=20.0, read=180.0, write=30.0, pool=10.0)
            )
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        print(delta, end="", flush=True)
                        if chunk_callback:
                            try:
                                res = chunk_callback(delta)
                                if asyncio.iscoroutine(res):
                                    await res
                            except Exception:
                                pass
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
        tool_registry: Any = None,
        chunk_callback=None) -> str:
        """Full tool-calling pipeline with session isolation and canonical AgentRuntime loop"""
        session = self.get_session(session_id)
        user_last = ""
        if session.messages:
            for m in reversed(session.messages):
                if m.get('role') == 'user':
                    user_last = m.get('content', '')
                    break

        messages = self.get_messages_with_memory(user_last, session_id)

        tr = tool_registry
        if not tr and tool_executor:
            class ToolExecutorAdapter:
                def __init__(self, exec_fn, schemas):
                    self._exec_fn = exec_fn
                    self.schemas = schemas
                async def execute(self, name: str, args: dict) -> str:
                    return await self._exec_fn(name, args)
                def get_schemas(self):
                    return self.schemas
            tr = ToolExecutorAdapter(tool_executor, tool_schemas)

        if getattr(self, 'dispatcher', None) and user_last and tr:
            try:
                dispatch_res = await self.dispatcher.dispatch(
                    user_prompt=user_last,
                    tool_registry=tr,
                    llm_client=self
                )
                if dispatch_res.get("handled"):
                    resp_text = dispatch_res.get("content", "") or "Done, sir."
                    self.add_assistant_message(resp_text, session_id=session_id)
                    self.last_agent_result = AgentResult(final_answer=resp_text, status="COMPLETE", tool_count=0, iterations=1, execution_trace=[])
                    return resp_text
            except Exception as e:
                print(f"[DISPATCHER] Dispatch error, falling back to direct pipeline: {e}")
        
        print(f"[PIPELINE] Calling API for session '{session.session_id}' with {len(tool_schemas)} tools")
        
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
            execution_trace = []
            status = "COMPLETE"

            registered = tool_registry.tools if tool_registry and hasattr(tool_registry, 'tools') else tool_schemas

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

                # Classify Response
                classification = classify_response(response, registered_tools=registered)

                if classification == ResponseClassification.TOOL_CALL:
                    tool_calls = normalize_tool_calls(response, registered_tools=registered)
                    tool_names = [tc['name'] for tc in tool_calls]
                    print(f"[AGENT] Tool call detected: {', '.join(tool_names)}")

                    tool_calls_data = []
                    for tc in tool_calls:
                        tool_calls_data.append({
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["arguments"])
                            }
                        })
                    messages.append({
                        "role": "assistant",
                        "content": "",
                        "tool_calls": tool_calls_data
                    })

                    tool_results = []
                    max_allowed_calls = 5
                    calls_to_process = tool_calls[:max_allowed_calls]
                    overflow_count = len(tool_calls) - max_allowed_calls
                    pending_confirmation = False

                    for tc in calls_to_process:
                        name = tc["name"]
                        args = tc["arguments"]

                        print(f"[AGENT] Executing tool")
                        try:
                            result = await tool_executor(name, args)
                            print(f"[AGENT] Tool completed successfully")
                        except Exception as te:
                            result = f"Tool Execution Error: {str(te)}"
                            print(f"[AGENT] Tool failed: {te}")

                        execution_trace.append({
                            "id": tc["id"],
                            "name": name,
                            "args": args,
                            "result": str(result)
                        })
                        tool_results.append(result)

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": str(result)
                        })

                        if "PENDING_CONFIRMATION" in str(result) or "CONFIRMATION REQUIRED" in str(result):
                            print(f"[PIPELINE] Risky tool '{name}' requires confirmation. Halting loop.")
                            pending_confirmation = True
                            final_response_text = str(result)
                            break

                    if pending_confirmation:
                        break

                    if overflow_count > 0 and not any("PENDING_CONFIRMATION" in str(r) or "CONFIRMATION REQUIRED" in str(r) for r in tool_results):
                        cap_notice = f"\n\n[NOTICE] Reached tool call execution cap of {max_allowed_calls} calls. {overflow_count} remaining call(s) paused requiring user approval."
                        tool_results.append(cap_notice)
                        final_response_text = "\n\n".join(str(r) for r in tool_results)
                        break

                    print("[AGENT] Continuing agent loop for synthesis")
                    continue
                else:
                    # Classification is FINAL
                    content_text = ""
                    if isinstance(response, str):
                        content_text = response
                    elif hasattr(response, 'choices') and response.choices:
                        msg = getattr(response.choices[0], 'message', None)
                        content_text = getattr(msg, 'content', '') or ""
                    elif hasattr(response, 'content'):
                        content_text = getattr(response, 'content', '') or ""
                    elif isinstance(response, dict):
                        content_text = response.get('content') or response.get('text') or ""

                    # FINAL RESPONSE FIREWALL CHECK
                    if is_unresolved_tool_call(content_text, registered_tools=registered):
                        print(f"[AGENT FIREWALL] Blocked unexecuted tool call JSON from final output. Routing back for execution.")
                        sec_calls = normalize_tool_calls(content_text, registered_tools=registered)
                        if sec_calls:
                            response = content_text
                            continue

                    print("[AGENT] Final response generated")
                    final_response_text = content_text
                    if chunk_callback and final_response_text:
                        try:
                            res = chunk_callback(final_response_text)
                            if asyncio.iscoroutine(res):
                                await res
                        except Exception:
                            pass
                    break

            if not final_response_text and execution_trace:
                final_response_text = "I have completed the requested tool operations, sir."

            api_latency = time.time() - api_t0
            response_text = final_response_text or "Done, sir."
            self.add_assistant_message(response_text, session_id=session_id)
            print(f"[PIPELINE] Response: {repr(response_text[:150])}")

            agent_result = AgentResult(
                final_answer=response_text,
                status=status,
                tool_count=len(execution_trace),
                iterations=current_turn,
                execution_trace=execution_trace
            )
            self.last_agent_result = agent_result

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


APIClient = JarvisAPIClient
