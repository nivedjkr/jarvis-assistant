"""
Unit & Integration Tests for AgentRuntime, Response Classifier, and Final Response Firewall.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from jarvis.tool_normalizer import (
    normalize_tool_calls, classify_response, is_unresolved_tool_call, ResponseClassification
)
from jarvis.api_client import APIClient, AgentResult


# --- TEST 1: Firewall Detection ---
def test_firewall_detection():
    registered_tools = {"web_search_live", "search_obsidian", "check_email"}

    # Raw tool calls MUST be detected as unresolved
    raw_tool_1 = '{"tool": "web_search_live", "args": {"query": "machine learning research internships summer 2026"}}'
    assert is_unresolved_tool_call(raw_tool_1, registered_tools) is True

    raw_tool_2 = '{"name": "check_email", "arguments": {"limit": 5}}'
    assert is_unresolved_tool_call(raw_tool_2, registered_tools) is True

    # Genuine text responses MUST pass firewall (return False)
    clean_text = "Here are the top machine learning research internships for summer 2026..."
    assert is_unresolved_tool_call(clean_text, registered_tools) is False


# --- TEST 2: Response Classification ---
def test_response_classification():
    registered_tools = {"web_search_live", "search_obsidian"}

    tool_call_resp = '{"tool": "web_search_live", "args": {"query": "test query"}}'
    assert classify_response(tool_call_resp, registered_tools) == ResponseClassification.TOOL_CALL

    final_resp = "I found 3 relevant papers on quantum computing."
    assert classify_response(final_resp, registered_tools) == ResponseClassification.FINAL


# --- TEST 3: Canonical Target Request Execution & Post-Tool Synthesis ---
@pytest.mark.asyncio
async def test_target_request_agent_runtime_loop():
    client = APIClient()

    # Mock provider to simulate multi-turn loop:
    # Turn 1: LLM requests web_search_live
    # Turn 2: LLM synthesizes findings into final answer
    mock_provider = MagicMock()

    turn1_resp = '{"tool": "web_search_live", "args": {"query": "machine learning research internships summer 2026"}}'
    turn2_resp = "Here are several top machine learning research internships for summer 2026: 1. OpenAI Research, 2. Google DeepMind..."

    call_count = 0
    async def mock_chat(messages, tools=None, max_tokens=2048):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return turn1_resp
        return turn2_resp

    mock_provider.chat = AsyncMock(side_effect=mock_chat)
    client.provider = mock_provider

    tool_schemas = [{
        "type": "function",
        "function": {
            "name": "web_search_live",
            "description": "Search live web",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}
        }
    }]

    executed_tools = []
    async def mock_executor(name: str, args: dict) -> str:
        executed_tools.append({"name": name, "args": args})
        return "Search Results: Found 5 ML internship openings for Summer 2026."

    session = client.new_session(title="Internship Test")
    client.add_user_message("Find machine learning research internships for summer 2026.", session_id=session.session_id)

    final_ans = await client.chat_with_tools(
        tool_schemas=tool_schemas,
        tool_executor=mock_executor,
        session_id=session.session_id,
        tool_registry=None
    )

    # Assertions
    assert len(executed_tools) == 1
    assert executed_tools[0]["name"] == "web_search_live"
    assert "machine learning research internships" in executed_tools[0]["args"]["query"]

    # Verify AgentResult
    agent_result = getattr(client, "last_agent_result", None)
    assert agent_result is not None
    assert agent_result.tool_count == 1
    assert agent_result.status == "COMPLETE"
    assert "OpenAI Research" in final_ans
    assert "{" not in final_ans  # Firewall check: no raw JSON in response


# --- TEST 4: Firewall Blocks Unresolved Tool Call Leaks ---
@pytest.mark.asyncio
async def test_firewall_blocks_raw_tool_json_leak():
    client = APIClient()

    call_count = 0
    async def mock_chat(messages, tools=None, max_tokens=2048):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return '{"tool": "web_search_live", "args": {"query": "python"}}'
        return "Here are the python search results."

    mock_provider = MagicMock()
    mock_provider.chat = AsyncMock(side_effect=mock_chat)
    client.provider = mock_provider

    tool_schemas = [{
        "type": "function",
        "function": {"name": "web_search_live", "parameters": {}}
    }]

    async def mock_executor(name: str, args: dict) -> str:
        return "Python results"

    session = client.new_session(title="Firewall Test")
    client.add_user_message("Search python", session_id=session.session_id)

    final_ans = await client.chat_with_tools(
        tool_schemas=tool_schemas,
        tool_executor=mock_executor,
        session_id=session.session_id,
        tool_registry=None
    )

    agent_result = getattr(client, "last_agent_result", None)
    assert agent_result is not None
    assert agent_result.tool_count > 0
    # Response must NOT be raw JSON
    assert not final_ans.startswith('{"tool"')
