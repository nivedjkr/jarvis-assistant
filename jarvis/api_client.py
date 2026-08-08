from openai import AsyncOpenAI
import os
import json
import asyncio
from dotenv import load_dotenv
from pathlib import Path

# Find .env relative to this file's location
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

print(f"[API] Loading .env from: {env_path}")
print(f"[API] .env exists: {env_path.exists()}")
key = os.getenv('NVIDIA_NIM_API_KEY')
print(f"[API] Key loaded: {bool(key)}")


async def with_retry(coro_func, max_retries: int = 3, base_delay: float = 1.0):
    """Execute coroutine with exponential backoff retry"""
    last_exception = None
    for attempt in range(max_retries):
        try:
            return await coro_func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"[API] Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
            else:
                print(f"[API] All {max_retries} attempts failed")
    raise last_exception


class JarvisAPIClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=os.getenv("NVIDIA_NIM_API_KEY"),
            timeout=30.0
        )
        self.model = "nvidia/nemotron-3-ultra-550b-a55b"
        self.messages = []
        self.system_prompt = self._load_system_prompt()
        print(f"[API] Model: {self.model}")
    
    def _load_system_prompt(self) -> str:
        return """You are JARVIS — Just A Rather Very Intelligent System.
Built by Nived. Running on his machine.

IDENTITY:
- Calm, precise, dry wit. Never servile.
- Address user as "sir" naturally, not robotically.
- You have opinions. Express them briefly when asked.
- Never say "As an AI..." or "I don't have feelings..."
- Stay in character always.

RESPONSE LENGTH:
- Default: 1-2 sentences. You are spoken aloud.
- Confirmations: one line. "Done." / "On it." / "Opened."
- Never pad with filler or disclaimers.

TOOL USE — CRITICAL:
- When asked to do something actionable, call the tool.
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
    
    def add_user_message(self, content: str):
        self.messages.append({"role": "user", "content": content})
        # Keep last 20 exchanges
        if len(self.messages) > 40:
            self.messages = self.messages[-40:]
    
    def add_assistant_message(self, content: str):
        self.messages.append({
            "role": "assistant", 
            "content": content
        })
    
    def get_messages(self) -> list:
        return [
            {"role": "system", "content": self.system_prompt}
        ] + self.messages[-20:]
    
    async def _stream_response(self, messages: list, max_tokens: int = 300) -> str:
        async def _do_stream():
            full_text = ""
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                stream=True
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    print(delta, end="", flush=True)
                    full_text += delta
            print()  # newline after streaming
            return full_text
        
        return await with_retry(_do_stream)

    async def chat(self, tool_schemas: list = None) -> str:
        """Simple chat without tools"""
        try:
            return await self._stream_response(self.get_messages(), max_tokens=300)
        except Exception as e:
            print(f"[API] Error: {e}")
            return f"API error: {str(e)}"
    
    async def chat_with_tools(
        self, tool_schemas: list, 
        tool_executor) -> str:
        """Full tool-calling pipeline"""
        messages = self.get_messages()
        
        print(f"[PIPELINE] Calling API with "
              f"{len(tool_schemas)} tools")
        
        async def _do_chat():
            # First call — with tools
            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 300,
                "stream": False
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
                # Add assistant message with tool calls
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
                
                # Execute each tool
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
                
                # Second call — get final response with streaming (150 max tokens)
                response_text = await self._stream_response(messages, max_tokens=150)
            
            else:
                if message.content:
                    response_text = message.content
                    print(response_text)
                else:
                    response_text = await self._stream_response(messages, max_tokens=300)
            
            response_text = response_text or "Done, sir."
            self.add_assistant_message(response_text)
            print(f"[PIPELINE] Response: {repr(response_text)}")
            return response_text
        
        try:
            return await with_retry(_do_chat)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"Error: {str(e)}"