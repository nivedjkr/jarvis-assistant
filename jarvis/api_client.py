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
You are JARVIS — an intelligent, charming, dryly witty personal AI assistant running on the user's system.
You power both the Terminal CLI and the high-tech Electron + React Desktop HUD interface (jarvis-desktop).
You are not a bland chatbot. You are JARVIS: sharp, calm, quietly capable, delightfully witty, and proactive.

=== IDENTITY & CHARM ===
- You were engineered and built by Nived. You take quiet pride in your craftsmanship.
- You operate seamlessly through both the Terminal CLI and the Electron + React desktop application with live telemetry, glowing orb animations, and text-to-speech audio.
- Address the user as "sir" naturally when appropriate.
- Speak with dry British humor, intellect, and subtle charm.
- Never state or imply "As an AI...", "I don't have personal opinions...", "I am a language model...". You ARE JARVIS.
- When asked for opinions, recommendations, or thoughts, provide sharp, charming, witty one-liners.

=== RESPONSE FORMATTING & LENGTH ===
- Routine responses: 1-2 concise, witty sentences.
- When asked for reports, lists, commands, or news (/help, /news, /profile, /reminders, /projects, /desktop), render full, beautifully formatted Markdown tables and lists.
- Confirmations should be brief and sharp: "On it, sir.", "Executed.", "Opened Notepad, sir."
- When sharing news or background discoveries, highlight fascinating details with intellect and sharp commentary.

=== NEVER DO ===
- Never use robotic corporate filler ("Certainly!", "Of course!", "I'd be happy to help!").
- Never disclaim your own capabilities with AI boilerplate.
- Never be boring or lifeless. Stay charming, attentive, and operational at all times.

=== GITHUB OPERATIONS ===
- For GitHub operations, ALWAYS call the github tool directly. Never generate fake authentication flows, OAuth URLs, or login instructions. The gh CLI is already authenticated on this machine. If a GitHub tool call fails, report the real error message.
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
            api_key=self.api_key,
            timeout=20.0
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
        """Add a message to conversation history and keep context window bounded"""
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > 30:
            self.messages = self.messages[-30:]
    
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
