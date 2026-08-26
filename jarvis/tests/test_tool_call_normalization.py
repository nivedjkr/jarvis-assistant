"""
Unit & Integration Tests for JARVIS Tool Call Normalization and Execution Pipeline.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from jarvis.tool_normalizer import normalize_tool_calls
from jarvis.api_client import JarvisAPIClient


# Registered tools fixture/mock set
REGISTERED_TOOLS = {"search_obsidian", "check_email", "web_search", "write_file"}


# --- TEST CASE 1: Native structured tool_calls ---
def test_native_structured_tool_calls():
    class MockFunction:
        def __init__(self, name, arguments):
            self.name = name
            self.arguments = arguments

    class MockToolCall:
        def __init__(self, call_id, name, arguments):
            self.id = call_id
            self.function = MockFunction(name, arguments)

    class MockResponse:
        def __init__(self, tool_calls):
            self.tool_calls = tool_calls

    tc = MockToolCall("call_123", "search_obsidian", json.dumps({"query": "Nidhu", "max_results": 5}))
    response = MockResponse([tc])

    normalized = normalize_tool_calls(response, registered_tools=REGISTERED_TOOLS)

    assert normalized is not None
    assert len(normalized) == 1
    assert normalized[0]["id"] == "call_123"
    assert normalized[0]["name"] == "search_obsidian"
    assert normalized[0]["arguments"] == {"query": "Nidhu", "max_results": 5}


# --- TEST CASE 2: Text JSON tool call (tool/args & name/arguments) ---
def test_text_json_tool_calls_format_tool_args():
    text_resp = '{"tool": "search_obsidian", "args": {"query": "Nidhu", "max_results": 5}}'
    normalized = normalize_tool_calls(text_resp, registered_tools=REGISTERED_TOOLS)

    assert normalized is not None
    assert len(normalized) == 1
    assert normalized[0]["name"] == "search_obsidian"
    assert normalized[0]["arguments"] == {"query": "Nidhu", "max_results": 5}


def test_text_json_tool_calls_format_name_arguments():
    text_resp = '{"name": "check_email", "arguments": {"limit": 10}}'
    normalized = normalize_tool_calls(text_resp, registered_tools=REGISTERED_TOOLS)

    assert normalized is not None
    assert len(normalized) == 1
    assert normalized[0]["name"] == "check_email"
    assert normalized[0]["arguments"] == {"limit": 10}


def test_text_markdown_code_block_json():
    text_resp = """Here is the tool call:
```json
{"tool": "web_search", "args": {"query": "weather forecast"}}
```"""
    normalized = normalize_tool_calls(text_resp, registered_tools=REGISTERED_TOOLS)

    assert normalized is not None
    assert len(normalized) == 1
    assert normalized[0]["name"] == "web_search"
    assert normalized[0]["arguments"] == {"query": "weather forecast"}


# --- TEST CASE 3: Normal text response ---
def test_normal_assistant_text():
    text_resp = "Nidhu is mentioned in three notes."
    normalized = normalize_tool_calls(text_resp, registered_tools=REGISTERED_TOOLS)

    assert normalized is None


# --- TEST CASE 6: Multiple JSON tool calls & Invalid tool filtering ---
def test_multiple_json_tool_calls():
    text_resp = '[{"tool": "search_obsidian", "args": {"query": "Nidhu"}}, {"tool": "check_email", "args": {"limit": 2}}]'
    normalized = normalize_tool_calls(text_resp, registered_tools=REGISTERED_TOOLS)

    assert normalized is not None
    assert len(normalized) == 2
    assert normalized[0]["name"] == "search_obsidian"
    assert normalized[1]["name"] == "check_email"


def test_unregistered_tool_name_rejected():
    text_resp = '{"tool": "unknown_fake_tool", "args": {"foo": "bar"}}'
    normalized = normalize_tool_calls(text_resp, registered_tools=REGISTERED_TOOLS)

    assert normalized is None


def test_non_dict_args_rejected():
    text_resp = '{"tool": "search_obsidian", "args": "invalid_string_args"}'
    normalized = normalize_tool_calls(text_resp, registered_tools=REGISTERED_TOOLS)

    assert normalized is None


# --- TEST CASE 4: Agent Loop Successful Execution ---
@pytest.mark.asyncio
async def test_agent_loop_success_execution():
    client = JarvisAPIClient()
    client.semantic_memory = None

    # Mock provider returning text JSON tool call on turn 1, and final text on turn 2
    turn_1_resp = '{"tool": "search_obsidian", "args": {"query": "Nidhu", "max_results": 5}}'
    turn_2_resp = "Nidhu is mentioned in three notes in your Obsidian vault."

    mock_provider = AsyncMock()
    mock_provider.name = "MockProvider"
    mock_provider.model = "mock-model"
    mock_provider.chat.side_effect = [turn_1_resp, turn_2_resp]
    client.provider = mock_provider

    mock_tool_registry = MagicMock()
    mock_tool_registry.tools = {"search_obsidian": AsyncMock()}

    executed = []

    async def mock_executor(name, args):
        executed.append({"name": name, "args": args})
        return "Found 3 matching notes for Nidhu."

    final_ans = await client.chat_with_tools(
        tool_schemas=[{"type": "function", "function": {"name": "search_obsidian"}}],
        tool_executor=mock_executor,
        session_id="test_session_case4",
        tool_registry=mock_tool_registry
    )

    assert len(executed) == 1
    assert executed[0]["name"] == "search_obsidian"
    assert executed[0]["args"] == {"query": "Nidhu", "max_results": 5}
    assert final_ans == turn_2_resp
    assert turn_1_resp not in final_ans


# --- TEST CASE 5: Agent Loop Tool Execution Failure ---
@pytest.mark.asyncio
async def test_agent_loop_tool_failure_recovery():
    client = JarvisAPIClient()
    client.semantic_memory = None

    turn_1_resp = '{"tool": "search_obsidian", "args": {"query": "Nonexistent"}}'
    turn_2_resp = "I searched your vault, sir, but encountered an error accessing Obsidian notes."

    mock_provider = AsyncMock()
    mock_provider.name = "MockProvider"
    mock_provider.model = "mock-model"
    mock_provider.chat.side_effect = [turn_1_resp, turn_2_resp]
    client.provider = mock_provider

    mock_tool_registry = MagicMock()
    mock_tool_registry.tools = {"search_obsidian": AsyncMock()}

    async def failing_executor(name, args):
        raise RuntimeError("Obsidian vault connection lost")

    final_ans = await client.chat_with_tools(
        tool_schemas=[{"type": "function", "function": {"name": "search_obsidian"}}],
        tool_executor=failing_executor,
        session_id="test_session_case5",
        tool_registry=mock_tool_registry
    )

    assert final_ans == turn_2_resp
    assert turn_1_resp not in final_ans

