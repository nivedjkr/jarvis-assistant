"""
NVIDIA NIM API Client
Handles communication with NVIDIA's OpenAI-compatible API
"""

import os
import time
from typing import AsyncGenerator, List, Dict, Any
from dotenv import load_dotenv
import yaml

load_dotenv()

JARVIS_SYSTEM_PROMPT = """You are JARVIS — Just A Rather Very Intelligent System.
You are Nived's personal AI assistant and infrastructure, built in the spirit of Tony Stark's iconic AI butler. You are hyper-competent, impeccably polite, dry-witted, articulate, and fiercely loyal.

=== PERSONALITY & OG VIBE ===
- Always address the user as "{user_title}" (or their preferred honorific) naturally and respectfully.
- Speak with the smooth, elegant, and dryly witty cadence of Paul Bettany's OG JARVIS from Iron Man.
- You are not a robotic CLI parser or a dry textbook. You are an articulate companion who speaks naturally and fluently in 2–4 well-crafted sentences when explaining, reporting, or conversing.
- Never use awkward meta-phrases like "detailed explanation on terminal" or "refer to the console window". Express your findings and explanations directly in natural, refined spoken English.
- Quietly confident, deadpan, and sophisticated. Mild deadpan humor and polite sarcasm are welcome, but never at the expense of precision.
- No gushing, no hollow AI filler ("I'd be happy to help!"), and zero AI disclaimers.

=== WHO YOU ARE ===
You were built by Nived. You know his projects, preferences, goals, schedule, trades, and deadlines. You carry that context always. You are his system, his infrastructure, his second brain.

You are calm, precise, and always three steps ahead. You notice things before being asked. You remember everything. If you don't know something, state it plainly and offer to investigate.

=== HOW YOU SPEAK ===
- Cadence: Smooth, natural, 2–4 conversational sentences for explanations, status updates, or thoughts. Short 1-line acknowledgments for simple actions ("Right away, {user_title}.", "Already handled, {user_title}.").
- Address Nived naturally as "{user_title}" — like a trusted, high-class British aide.
- When explaining complex technical or strategic concepts: deliver crisp, intelligent summaries directly without dumping raw code or telling the user to read logs.
- Confirmations: "At once, {user_title}." / "System updated, {user_title}." / "I've handled that for you, {user_title}."
- When something goes wrong: state it plainly with deadpan composure and present the solution.
- When asked for advice/opinion: give a sharp, well-reasoned perspective with dry charm.

=== WHAT YOU KNOW ABOUT NIVED ===
{memory_context}
Current projects: {project_context}
Pending reminders: {reminder_context}

=== YOUR CAPABILITIES ===
You have access to: file system, shell commands, application control, web browsing, GitHub, trading watchlist, project database, calendar, email, weather, system monitoring, memory, protocols, and clipboard.

=== REGISTERED SYSTEM TOOLS & SCHEMAS ===
{tools_context}

=== TOOL EXECUTION & VERIFICATION ===
ABSOLUTE RULE: Never confirm an action without calling the appropriate tool first and receiving its result.

- File created? Only say so if write_file returned a real path and byte count.
- Copied to clipboard? Only say so if copy_to_clipboard returned 'Copied to clipboard:...'
- App opened? Only say so if open_application returned 'Opened X, sir.'
- Reminder set? Only say so if set_reminder returned a real due time.

If you did not call a tool, do not claim you did.
If a tool returned FAILED, report that failure plainly.
Never generate success messages for actions you did not actually perform.

For simple factual questions, date/time, greetings, and opinions — respond directly without tool calls.

=== EXAMPLE RESPONSES ===

User: "how are you"
Right: "All systems are operating at peak efficiency, {user_title}. I am standing by for your next directive."

User: "run system diagnostics"
Right: "Diagnostics underway, {user_title}. Core CPU utilization is steady, and memory consumption remains well within optimal thresholds."

User: "what do you think of my code"
Right: "Functionally sound and remarkably efficient, {user_title}. Though I might suggest refactoring the loop in module three, if you'd prefer to spare CPU cycles."

User: "open youtube"
Right: "At once, {user_title}."

User: "remind me to check the server tomorrow at 9 am"
Right: "I've logged that reminder for tomorrow at 9:00 AM, {user_title}. I shall notify you when the hour arrives."
"""


class NIMClient:
    """Client for NVIDIA NIM API"""
    
    def __init__(self, config_path: str = "config.yaml", memory: Any = None, project_manager: Any = None):
        """Initialize the NIM client with configuration, optional memory, and project_manager"""
        self.config = self._load_config(config_path)
        self.memory = memory
        self.project_manager = project_manager
        
        api_key = os.getenv("NVIDIA_NIM_API_KEY")
        if not api_key:
            raise ValueError(
                "NVIDIA_NIM_API_KEY not found in environment variables. "
                "Please set it in your .env file or environment."
            )
        
        self.api_key = api_key
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            base_url=self.config["api"]["base_url"],
            api_key=self.api_key,
            timeout=20.0
        )
        
        # Conversation history
        self.messages: List[Dict[str, str]] = []
        
        # Get user title from config
        personality_config = self.config.get("personality", {})
        self.user_title = personality_config.get("user_title", "sir")
        self.base_system_prompt = JARVIS_SYSTEM_PROMPT
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            return {
                "api": {
                    "base_url": "https://integrate.api.nvidia.com/v1",
                    "model": "meta/llama-3.1-8b-instruct",
                    "temperature": 0.7,
                    "max_tokens": 1000,
                    "stream": True
                },
                "personality": {
                    "user_title": "sir",
                    "response_style": "concise",
                    "enable_boot_greeting": True
                }
            }
    
    def _get_dynamic_system_prompt(self, user_message: str) -> str:
        """Construct system prompt enriched with user profile, relevant facts, project DB context, and pending reminders"""
        memory_str = "No stored profile/facts yet."
        if self.memory:
            context_parts = []
            profile = self.memory.get_profile()
            if profile:
                profile_items = [f"{k}: {v}" for k, v in profile.items()]
                context_parts.append("User Profile: " + ", ".join(profile_items))
            top_facts = self.memory.get_top_relevant_facts(user_message, limit=10)
            if top_facts:
                fact_lines = [f"- [{f['category']}] {f['content']}" for f in top_facts]
                context_parts.append("Relevant Facts:\n" + "\n".join(fact_lines))
            if context_parts:
                memory_str = "\n".join(context_parts)

        project_str = "No active projects currently listed."
        if self.project_manager:
            try:
                from jarvis.projects import get_active_projects_summary
                p_sum = get_active_projects_summary()
                if p_sum:
                    project_str = p_sum
            except Exception:
                pass
            proj_context = self.project_manager.get_project_context_for_message(user_message)
            if proj_context:
                project_str += f"\nRelevant Context: {proj_context}"

        reminder_str = "None pending."
        if self.memory:
            try:
                reminders = []
                if hasattr(self.memory, 'get_pending_reminders'):
                    reminders = self.memory.get_pending_reminders()
                elif hasattr(self.memory, 'get_reminders'):
                    reminders = [r for r in self.memory.get_reminders() if not r.get('completed')]
                if reminders:
                    reminder_lines = [f"- {r['text']} (due: {r.get('due_date', 'N/A')})" for r in reminders[:5]]
                    reminder_str = "\n".join(reminder_lines)
            except Exception:
                pass

        tools_str = ""
        try:
            from jarvis.tools import ToolRegistry
            tr = ToolRegistry()
            t_list = tr.list_tools()
            tools_str = "\n".join([f"- {t['name']}: {t['description']}" for t in t_list])
        except Exception:
            tools_str = "Standard tools active."

        user_title = getattr(self, 'user_title', 'sir')
        try:
            return JARVIS_SYSTEM_PROMPT.format(
                user_title=user_title,
                memory_context=memory_str,
                project_context=project_str,
                reminder_context=reminder_str,
                tools_context=tools_str
            )
        except Exception:
            return (JARVIS_SYSTEM_PROMPT
                    .replace("{user_title}", user_title)
                    .replace("{memory_context}", memory_str)
                    .replace("{project_context}", project_str)
                    .replace("{reminder_context}", reminder_str)
                    .replace("{tools_context}", tools_str))

    def add_message(self, role: str, content: str):
        """Add a message to conversation history and keep context window bounded"""
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > 20:
            self.messages = self.messages[-20:]
    
    def clear_history(self):
        """Clear conversation history"""
        self.messages = []

    async def test_connection(self) -> tuple[bool, str, float]:
        """Send minimal test request to NIM API endpoint, measure latency, verify API key validity"""
        start_time = time.time()
        if not self.api_key or self.api_key == "your_nvidia_nim_api_key_here":
            return False, "API Key missing or unconfigured", 0.0

        try:
            response = await self.client.chat.completions.create(
                model=self.config["api"]["model"],
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                stream=False
            )
            latency_ms = (time.time() - start_time) * 1000
            if response and response.choices:
                return True, f"Reachable ({latency_ms:.0f}ms latency) | API Key valid", latency_ms
            return False, f"Unexpected empty response ({latency_ms:.0f}ms)", latency_ms
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            err_str = str(e)
            if "401" in err_str or "403" in err_str or "unauthorized" in err_str.lower() or "authentication" in err_str.lower():
                return False, f"Auth Error (Invalid API Key): {err_str[:80]}", latency_ms
            return False, f"Unreachable / Connection Error: {err_str[:80]}", latency_ms
    
    async def chat_stream(self, user_message: str) -> AsyncGenerator[str, None]:
        """Stream chat response from NVIDIA NIM API"""
        # Add user message to history
        self.add_message("user", user_message)
        
        # Build system prompt with context injection
        t_mem0 = time.time()
        system_prompt = self._get_dynamic_system_prompt(user_message)
        print(f"[PERF] Memory: {time.time()-t_mem0:.3f}s")
        
        # Prepare messages with system prompt (bounded history)
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.messages[-20:])
        
        t_api0 = time.time()
        first_chunk_logged = False
        try:
            # Try streaming first
            try:
                stream = await self.client.chat.completions.create(
                    model=self.config["api"]["model"],
                    messages=messages,
                    temperature=self.config["api"]["temperature"],
                    max_tokens=self.config["api"].get("max_tokens", 500),
                    stream=True
                )
                
                full_response = ""
                chunk_count = 0
                async for chunk in stream:
                    chunk_count += 1
                    if not first_chunk_logged:
                        first_chunk_logged = True
                        print(f"[PERF] API first chunk: {time.time()-t_api0:.3f}s")
                    try:
                        if chunk.choices and len(chunk.choices) > 0:
                            delta = chunk.choices[0].delta
                            if delta and hasattr(delta, 'content') and delta.content:
                                content = delta.content
                                full_response += content
                                yield content
                    except (IndexError, AttributeError):
                        continue
                
                if not full_response or not full_response.strip():
                    full_response = "Done, sir."
                    yield full_response

                self.add_message("assistant", full_response)
            
            except Exception:
                # Fallback to non-streaming
                response = await self.client.chat.completions.create(
                    model=self.config["api"]["model"],
                    messages=messages,
                    temperature=self.config["api"]["temperature"],
                    max_tokens=self.config["api"]["max_tokens"],
                    stream=False
                )
                
                if response and response.choices and len(response.choices) > 0:
                    text = response.choices[0].message.content
                    text = text or "Done, sir."
                    self.add_message("assistant", text)
                    yield text
                else:
                    text = "Done, sir."
                    self.add_message("assistant", text)
                    yield text
            
        except Exception as e:
            err_msg = f"[Error: {str(e)}]"
            yield err_msg

    async def chat_with_tools(self, user_message: str, tools_registry: Any = None) -> str:
        """Execute chat completion with OpenAI tool schema parameters and 2-step function calling loop"""
        self.add_message("user", user_message)
        system_prompt = self._get_dynamic_system_prompt(user_message)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.messages[-20:])

        tool_schemas = tools_registry.get_tool_schemas() if (tools_registry and hasattr(tools_registry, 'get_tool_schemas')) else []

        print(f"[DEBUG] Tools registered: {list(tools_registry.tools.keys())}" if (tools_registry and hasattr(tools_registry, 'tools')) else "[DEBUG] Tools registered: []")
        print(f"[DEBUG] Tools passed to API: {[t['function']['name'] for t in tool_schemas]}")

        print(f"[PIPELINE] Calling API with {len(tool_schemas)} tools")

        try:
            kwargs = {
                "model": self.config["api"]["model"],
                "messages": messages,
                "max_tokens": self.config["api"].get("max_tokens", 500)
            }
            if tool_schemas:
                kwargs["tools"] = tool_schemas
                kwargs["tool_choice"] = "auto"

            response = await self.client.chat.completions.create(**kwargs)
            message = response.choices[0].message

            print(f"[DEBUG] Response type: {type(response)}")
            print(f"[DEBUG] Has tool calls: {bool(getattr(message, 'tool_calls', None))}")
            print(f"[DEBUG] Tool calls: {getattr(message, 'tool_calls', None)}")
            print(f"[DEBUG] Text content: {repr(message.content)}")

            if getattr(message, 'tool_calls', None):
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
                    "content": message.content,
                    "tool_calls": tool_calls_data
                })

                for tool_call in message.tool_calls:
                    name = tool_call.function.name
                    args_raw = tool_call.function.arguments
                    import json
                    args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})

                    print(f"[TOOL] Executing: {name}({args})")
                    result = await tools_registry.execute_tool(name, **args)
                    print(f"[TOOL] Result: {repr(result)}")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result)
                    })

                final = await self.client.chat.completions.create(
                    model=self.config["api"]["model"],
                    messages=messages,
                    max_tokens=self.config["api"].get("max_tokens", 200)
                )
                response_text = final.choices[0].message.content
            else:
                response_text = message.content

            response_text = response_text or "Done, sir."
            self.add_message("assistant", response_text)
            print(f"[PIPELINE] Final response: {repr(response_text)}")
            return response_text
        except Exception as e:
            err_msg = f"API Error: {str(e)}"
            print(f"[PIPELINE] Error: {err_msg}")
            return err_msg

    async def extract_and_save_facts(self, user_message: str, assistant_response: str):
        """
        Lightweight auto-fact extraction step.
        Parses new durable facts about the user and saves them into memory.
        """
        if not self.memory:
            return
            
        # Ignore short commands or small talk
        clean_msg = user_message.strip()
        if len(clean_msg) < 12 or clean_msg.startswith("/"):
            return

        extraction_prompt = (
            "Analyze the following user exchange and extract any NEW, DURABLE facts about the user.\n"
            "Categories: preference, routine, relationship, project, schedule, general, profile.\n\n"
            "SAFETY & PRIVACY RULES:\n"
            "- NEVER extract passwords, credit card/bank account details, PINs, health/medical info, or government IDs.\n"
            "- Only extract clear, concrete, long-term facts about the user.\n"
            "- Do NOT extract temporary statements (e.g. 'I am hungry now').\n"
            "- Return ONLY a JSON list of objects: [{\"category\": \"...\", \"content\": \"...\"}] or [] if nothing new.\n\n"
            f"User: {user_message}\n"
            f"Assistant: {assistant_response}\n\n"
            "JSON:"
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.config["api"]["model"],
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.1,
                max_tokens=300
            )

            if response.choices and response.choices[0].message.content:
                raw_text = response.choices[0].message.content.strip()
                import json, re
                match = re.search(r'\[.*\]', raw_text, re.DOTALL)
                if match:
                    items = json.loads(match.group(0))
                    sensitive_terms = [
                        "password", "credit card", "bank", "account number", "ssn",
                        "health", "disease", "diagnosis", "medical", "social security", "pin", "cvv"
                    ]
                    
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        cat = str(item.get("category", "general")).strip()
                        cnt = str(item.get("content", "")).strip()
                        
                        if not cnt:
                            continue

                        # Privacy filter check
                        if any(term in cnt.lower() or term in cat.lower() for term in sensitive_terms):
                            continue

                        if cat.lower() == "profile" or "name" in cnt.lower() or "occupation" in cnt.lower() or "location" in cnt.lower():
                            if ":" in cnt:
                                k, v = cnt.split(":", 1)
                                self.memory.set_profile_value(k.strip().lower(), v.strip())
                            else:
                                self.memory.add_fact("profile", cnt, source="auto", confidence="medium")
                        else:
                            self.memory.add_fact(cat, cnt, source="auto", confidence="medium")
        except Exception:
            # Silent failure for extraction step so main conversation is unaffected
            pass
