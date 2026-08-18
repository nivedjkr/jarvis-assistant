"""
Unit tests for Stage 1 of JARVIS Mk4 Agentic Layer
Tests BaseAgent, TaskTracker, and AgenticLoop without modifying existing tools.
"""

import pytest
import asyncio
from jarvis.agents.base_agent import BaseAgent, AgentResponse
from jarvis.orchestration.task_tracker import TaskTracker, TaskItem, TaskStatus
from jarvis.orchestration.agentic_loop import AgenticLoop
from jarvis.tools import ToolRegistry


def test_base_agent_tool_filtering():
    registry = ToolRegistry()
    
    agent_all = BaseAgent(name="TestAll", role_description="Test", system_prompt="Test")
    schemas_all = agent_all.get_tool_schemas(registry)
    assert len(schemas_all) > 10

    allowed = {"web_search", "read_file"}
    agent_scoped = BaseAgent(name="TestScoped", role_description="Test", system_prompt="Test", allowed_tools=allowed)
    schemas_scoped = agent_scoped.get_tool_schemas(registry)
    assert len(schemas_scoped) == 2
    names = {s["function"]["name"] for s in schemas_scoped}
    assert names == allowed


def test_task_tracker_lifecycle():
    tracker = TaskTracker()
    task = tracker.create_task(description="Test task", assigned_agent="TestAgent")
    assert task.task_id.startswith("task_")
    assert task.status == TaskStatus.PENDING

    tracker.update_task(task.task_id, status=TaskStatus.RUNNING, current_step="Step 1")
    updated = tracker.get_task(task.task_id)
    assert updated.status == TaskStatus.RUNNING
    assert updated.current_step == "Step 1"

    tracker.update_task(task.task_id, status=TaskStatus.COMPLETED, result="Done")
    completed = tracker.get_task(task.task_id)
    assert completed.status == TaskStatus.COMPLETED
    assert completed.result == "Done"


@pytest.mark.asyncio
async def test_agentic_loop_security_confirmation_halt():
    registry = ToolRegistry()
    loop = AgenticLoop(max_iterations=3)
    tracker = TaskTracker()
    agent = BaseAgent("TestSystem", "System role", "System prompt", allowed_tools={"run_command"})

    class MockMsg:
        tool_calls = [
            type("TC", (), {
                "id": "tc123",
                "function": type("Fn", (), {
                    "name": "run_command",
                    "arguments": '{"command": "rm -rf /"}'
                })()
            })()
        ]
        content = None

    class MockResp:
        choices = [type("Choice", (), {"message": MockMsg()})()]

    class MockLLM:
        model = "test-model"
        provider = None
        class Client:
            class Chat:
                class Completions:
                    async def create(self, **kwargs):
                        return MockResp()
                completions = Completions()
            chat = Chat()
        client = Client()

    res = await loop.run(
        agent=agent,
        user_prompt="Run risky command",
        tool_registry=registry,
        llm_client=MockLLM(),
        task_tracker=tracker
    )

    assert res.status == "WAITING_FOR_CONFIRMATION"
    assert "PENDING_CONFIRMATION" in res.content
