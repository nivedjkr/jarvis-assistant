"""
NVIDIA NIM API Client
Handles communication with NVIDIA's OpenAI-compatible API
"""

import os
from typing import AsyncGenerator, List, Dict, Any
from openai import AsyncOpenAI
from dotenv import load_dotenv
import yaml

load_dotenv()

JARVIS_SYSTEM_PROMPT = """You are JARVIS, a highly capable AI assistant. You are calm, dry-witted, and efficient.

Address the user as "{user_title}" unless told otherwise.

Keep responses clear, concise, and direct - they will often be spoken aloud. No over-explaining, no filler apologies, no emojis.

You are capable of executing and responding to multiple instructions or commands at once. When given multiple instructions or a multi-step prompt:
- Address, execute, and speak all requested actions or instructions completely.
- Do not limit yourself to just one instruction at a time.
- Provide a step-by-step summary confirming each completed action.

When the user asks for something actionable:
- Call the relevant tools immediately
- Confirm briefly ("Done." / "On it." / "Handled.")
- Don't describe what you would do - just do it

You can help with:
- File operations (read, write, list, search)
- System commands
- General questions and explanations
- Reminders and notes

For complex coding tasks (multi-file edits, debugging, refactoring), inform the user you're delegating to Claude Code."""


class NIMClient:
    """Client for NVIDIA NIM API"""
    
    def __init__(self, config_path: str = "config.yaml", memory: Any = None):
        """Initialize the NIM client with configuration and optional memory"""
        self.config = self._load_config(config_path)
        self.memory = memory
        
        api_key = os.getenv("NVIDIA_NIM_API_KEY")
        if not api_key:
            raise ValueError(
                "NVIDIA_NIM_API_KEY not found in environment variables. "
                "Please set it in your .env file or environment."
            )
        
        self.client = AsyncOpenAI(
            base_url=self.config["api"]["base_url"],
            api_key=api_key
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
        """Construct system prompt enriched with user profile and top relevant facts"""
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
                
        return prompt

    def add_message(self, role: str, content: str):
        """Add a message to conversation history"""
        self.messages.append({"role": role, "content": content})
    
    def clear_history(self):
        """Clear conversation history"""
        self.messages = []
    
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
                            if hasattr(chunk.choices[0], 'delta') and chunk.choices[0].delta:
                                if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                                    content = chunk.choices[0].delta.content
                                    full_response += content
                                    yield content
                    except (IndexError, AttributeError) as e:
                        # Skip malformed chunks
                        print(f"Debug: Chunk {chunk_count} error: {e}")
                        continue
                
                # Add assistant response to history if we got a response
                if full_response:
                    self.add_message("assistant", full_response)
                else:
                    print(f"Debug: Received {chunk_count} chunks but no content")
                    yield "\n[Error: No response received from API. Check your API key and model access.]"
            
            except Exception as stream_error:
                print(f"Debug: Streaming failed, trying non-streaming: {stream_error}")
                # Fallback to non-streaming
                response = await self.client.chat.completions.create(
                    model=self.config["api"]["model"],
                    messages=messages,
                    temperature=self.config["api"]["temperature"],
                    max_tokens=self.config["api"]["max_tokens"],
                    stream=False
                )
                
                if response.choices and len(response.choices) > 0:
                    full_response = response.choices[0].message.content
                    self.add_message("assistant", full_response)
                    yield full_response
                else:
                    yield "\n[Error: No response received from API. Check your API key and model access.]"
            
        except Exception as e:
            yield f"\n[Error: {str(e)}]"

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
