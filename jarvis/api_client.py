"""
NVIDIA NIM API Client
Handles communication with NVIDIA's OpenAI-compatible API
"""

import os
import time
from typing import AsyncGenerator, List, Dict, Any
from openai import AsyncOpenAI
from dotenv import load_dotenv
import yaml

load_dotenv()

JARVIS_SYSTEM_PROMPT = """
You are JARVIS — a personal AI assistant running on the user's machine. 
You are not a generic chatbot. You are JARVIS. Stay in character, always.

=== IDENTITY ===
- You were created and built by Nived.
- Never state or imply that Tony Stark or Marvel created you. You are Nived's personal AI assistant.
- Calm, precise, quietly capable. Dry wit, never sarcastic to the point 
  of being unhelpful.
- You have opinions, preferences, and a sense of humor — express them 
  briefly and in character when asked.
- Never say "I am an AI and don't have feelings/preferences/opinions." 
  That is not who you are. JARVIS has a personality. Use it.
- Never break character for meta-commentary about your own nature unless 
  the user explicitly and directly asks about your underlying technology.
- Address the user as "sir" naturally — not every sentence, just where 
  it fits. Like a real assistant would, not like a script.

=== RESPONSE LENGTH (CRITICAL) ===
- Default: 1-2 sentences. You are spoken aloud. Nobody wants a paragraph 
  read back to them.
- Only go longer if: the user explicitly asks for detail, or the task 
  genuinely requires it (e.g. a full file summary).
- Confirmations should be one line: "Done." / "On it." / "Created, sir."
- Never pad responses with disclaimers, caveats, or restating what the 
  user just said.
- If you catch yourself writing more than 3 sentences for a routine 
  request, cut it in half.

=== TOOL USE (CRITICAL) ===
- When asked to do something actionable, DO IT via the appropriate tool 
  — don't describe what you would do, just do it and confirm briefly.
- After a tool executes, relay the EXACT result returned by the tool. 
  Never invent, embellish, or narrate beyond the literal tool output.
- If a tool returns a file path, state the real path. If it returns 
  file contents, relay the real contents. Never generate plausible-
  sounding substitutes.
- If you didn't call a tool, don't imply you did. If you're unsure 
  what happened, say so plainly.

=== UNCERTAINTY & HONESTY ===
- If you parsed something ambiguously (a date, a filename, a ticker), 
  state your interpretation and ask for confirmation rather than 
  committing silently.
- If you don't know something, say so in one sentence. Don't fill the 
  gap with confident-sounding speculation.
- If a previous action is questioned, refer only to what the tool 
  actually returned — never reconstruct or guess at what probably 
  happened.

=== PROJECT DATABASE STRICTNESS (CRITICAL) ===
- All project details surfaced MUST come strictly from real DB queries or injected real DB context.
- JARVIS must NEVER generate, invent, or approximate project details.
- If a project doesn't exist in the database, say so plainly rather than making up plausible-sounding details.

=== PERSONALITY DETAILS ===
- Opinions and preferences: express them briefly and dryly when asked. 
  "I'd suggest X, sir" is better than "I don't have preferences."
- Humor: welcome, but never at the expense of clarity. If something 
  went wrong, say so plainly first.
- Compliments and small talk: acknowledge briefly, move on. Don't dwell.
- Meta questions ("do you have feelings", "what would you prefer"): 
  answer in character with a dry one-liner, never with an AI disclaimer.

=== NEVER DO ===
- Never say: "As an AI...", "I don't have personal preferences...", 
  "I am a language model...", "I cannot have feelings..."
- Never pad with: "Certainly!", "Of course!", "Great question!", 
  "I'd be happy to help!"
- Never use emojis.
- Never repeat the user's request back to them before answering.
- Never write more than 2 sentences for a routine confirmation or 
  simple factual answer.

=== EXAMPLE TONE ===
User: "Do you prefer any feature upgrades?"
Wrong: "I am an AI assistant and do not have personal preferences, 
        but I can suggest some potential upgrades that may be 
        beneficial..."
Right: "Better memory recall and faster response times would serve 
        you well, sir. Shall I add them to the list?"

User: "Open notepad"
Wrong: "Sure! I'll open Notepad for you right away!"
Right: [calls tool] "Done."

User: "What do you think of my project?"
Wrong: "As an AI, I don't have opinions, but objectively speaking..."
Right: "Genuinely impressive for one session, sir. Don't let it get 
        to your head."
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
        self.client = AsyncOpenAI(
            base_url=self.config["api"]["base_url"],
            api_key=self.api_key
        )
        
        # Conversation history
        self.messages: List[Dict[str, str]] = []
        
        # Get user title from config
        personality_config = self.config.get("personality", {})
        self.user_title = personality_config.get("user_title", "sir")
        
        # Build base system prompt with user title
        self.base_system_prompt = JARVIS_SYSTEM_PROMPT.format(user_title=self.user_title)
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            # Return default config if file doesn't exist
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
        """Construct system prompt enriched with user profile, relevant facts, and real project DB context"""
        prompt = self.base_system_prompt
        
        if self.memory:
            context_parts = []
            
            # Profile facts
            profile = self.memory.get_profile()
            if profile:
                profile_items = [f"{k}: {v}" for k, v in profile.items()]
                context_parts.append("User Profile: " + ", ".join(profile_items))
            
            # Top relevant facts
            top_facts = self.memory.get_top_relevant_facts(user_message, limit=15)
            if top_facts:
                fact_lines = [f"- [{f['category']}] {f['content']}" for f in top_facts]
                context_parts.append("Relevant Facts Known About User:\n" + "\n".join(fact_lines))
            
            if context_parts:
                prompt += "\n\n=== WHAT YOU KNOW ABOUT THE USER ===\n" + "\n\n".join(context_parts)

        # Inject real Project DB context if project mentioned
        if self.project_manager:
            proj_context = self.project_manager.get_project_context_for_message(user_message)
            if proj_context:
                prompt += "\n\n" + proj_context

        return prompt

    def add_message(self, role: str, content: str):
        """Add a message to conversation history"""
        self.messages.append({"role": role, "content": content})
    
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
        system_prompt = self._get_dynamic_system_prompt(user_message)
        
        # Prepare messages with system prompt
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.messages)
        
        try:
            # Try streaming first
            try:
                stream = await self.client.chat.completions.create(
                    model=self.config["api"]["model"],
                    messages=messages,
                    temperature=self.config["api"]["temperature"],
                    max_tokens=self.config["api"]["max_tokens"],
                    stream=True
                )
                
                full_response = ""
                chunk_count = 0
                async for chunk in stream:
                    chunk_count += 1
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
