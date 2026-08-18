"""
BaseAgent for JARVIS Mk4 Agentic Layer
Provides lightweight shared functionality for logical agent roles.
All agents use the existing LLM provider and execute tools exclusively
through the existing ToolRegistry and security gate.
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
import asyncio


@dataclass
class AgentResponse:
    agent_name: str
    content: str
    status: str = "COMPLETED"  # COMPLETED, FAILED, WAITING_FOR_CONFIRMATION, IN_PROGRESS
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    pending_action_id: Optional[str] = None
    error: Optional[str] = None


class BaseAgent:
    """
    Lightweight base logical agent role.
    An agent is defined by a name, system instructions, and allowed tool scope.
    It does NOT run a separate LLM process or replace the ToolRegistry.
    """

    def __init__(
        self,
        name: str,
        role_description: str,
        system_prompt: str,
        allowed_tools: Optional[Set[str]] = None
    ):
        self.name = name
        self.role_description = role_description
        self.system_prompt = system_prompt
        self.allowed_tools = allowed_allowed_tools = set(allowed_tools) if allowed_tools is not None else None

    def get_tool_schemas(self, tool_registry) -> List[Dict[str, Any]]:
        """Filter tool registry schemas to only include allowed tools for this agent role."""
        if hasattr(tool_registry, 'get_schemas'):
            all_schemas = tool_registry.get_schemas()
        else:
            all_schemas = getattr(tool_registry, 'schemas', [])

        if self.allowed_tools is None:
            return all_schemas
        return [
            s for s in all_schemas
            if s.get("function", {}).get("name") in self.allowed_tools
        ]

    def build_system_message(self, extra_instructions: str = "") -> str:
        """Construct system message for LLM prompt context."""
        full_prompt = f"Role: {self.name}\nDescription: {self.role_description}\n\nDirectives:\n{self.system_prompt}"
        if extra_instructions:
            full_prompt += f"\n\nTask Instructions:\n{extra_instructions}"
        return full_prompt

    async def step(
        self,
        messages: List[Dict[str, Any]],
        tool_registry,
        llm_client,
        max_tokens: int = 400
    ) -> Dict[str, Any]:
        """
        Execute one reasoning step via LLM provider.
        Returns model response dictionary with text content and optional tool calls.
        """
        schemas = self.get_tool_schemas(tool_registry)
        
        # Build prompt with agent system prompt
        full_messages = [
            {"role": "system", "content": self.build_system_message()}
        ] + [m for m in messages if m.get("role") != "system"]

        if hasattr(llm_client.provider, 'chat'):
            response = await llm_client.provider.chat(full_messages, tools=schemas, max_tokens=max_tokens)
        else:
            response = await llm_client.client.chat.completions.create(
                model=llm_client.model,
                messages=full_messages,
                tools=schemas if schemas else None,
                tool_choice="auto" if schemas else None,
                max_tokens=max_tokens,
                stream=False
            )
            
        return response
