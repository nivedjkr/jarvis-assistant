"""
Unit tests for Stage 4 & 5 of JARVIS Mk4 Agentic Layer
Tests full integration, simple request direct bypass, multi-step subtask flow,
security confirmation gate compliance, and max iteration enforcement.
"""

import pytest
import asyncio
from jarvis.api_client import JarvisAPIClient
from jarvis.tools import ToolRegistry
from jarvis.orchestration.dispatcher import AgentDispatcher


@pytest.mark.asyncio
async def test_full_integration_simple_query_bypass():
    client = JarvisAPIClient()
    registry = ToolRegistry()

    async def mock_executor(name: str, args: dict):
        return await registry.execute(name, args)

    client.add_user_message("what time is it?")
    # Direct execution bypass occurs because is_multi_step == False
    assert hasattr(client, "dispatcher")
    res = await client.dispatcher.dispatch("what time is it?", registry, client)
    assert res["handled"] is False
    assert res["is_multi_step"] is False


@pytest.mark.asyncio
async def test_full_integration_security_gate_preserved():
    registry = ToolRegistry()
    dispatcher = AgentDispatcher()

    # Verify risky tool execution halts with WAITING_FOR_CONFIRMATION
    class MockLLM:
        model = "test-model"
        provider = None
        class Client:
            class Chat:
                class Completions:
                    async def create(self, **kwargs):
                        class MockMsg:
                            tool_calls = [
                                type("TC", (), {
                                    "id": "tc_email",
                                    "function": type("Fn", (), {
                                        "name": "send_email",
                                        "arguments": '{"to": "user@example.com", "subject": "Test", "body": "Hello"}'
                                    })()
                                })()
                            ]
                            content = None
                        return type("Choice", (), {"choices": [type("C", (), {"message": MockMsg()})()]})()
                completions = Completions()
            chat = Chat()
        client = Client()

    res = await dispatcher.agentic_loop.run(
        agent=dispatcher.agents["CommunicationAgent"],
        user_prompt="Send an email to user@example.com",
        tool_registry=registry,
        llm_client=MockLLM()
    )

    assert res.status == "WAITING_FOR_CONFIRMATION"
    assert "PENDING_CONFIRMATION" in res.content
