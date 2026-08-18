"""
Unit tests for Stage 3 of JARVIS Mk4 Agentic Layer
Tests PlanningAgent rule-based path, plan generation, and AgentDispatcher bypass for simple queries.
"""

import pytest
from jarvis.agents.planning_agent import PlanningAgent
from jarvis.orchestration.dispatcher import AgentDispatcher
from jarvis.tools import ToolRegistry


def test_planning_agent_rule_based_classification():
    planner = PlanningAgent()
    
    plan1 = planner.classify_request_rule_based("what time is it?")
    assert plan1 is not None
    assert plan1.is_multi_step is False

    plan2 = planner.classify_request_rule_based("check email")
    assert plan2 is not None
    assert plan2.is_multi_step is False

    plan3 = planner.classify_request_rule_based("Build a complete web application with React backend and SQLite database")
    assert plan3 is None


@pytest.mark.asyncio
async def test_dispatcher_simple_request_bypass():
    dispatcher = AgentDispatcher()
    registry = ToolRegistry()

    class DummyLLM:
        pass

    result = await dispatcher.dispatch(
        user_prompt="what time is it?",
        tool_registry=registry,
        llm_client=DummyLLM()
    )

    assert result["handled"] is False
    assert result["is_multi_step"] is False
