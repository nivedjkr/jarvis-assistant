"""
Unit tests for Stage 2 of JARVIS Mk4 Agentic Layer
Tests specialized agents (ResearchAgent, CodingAgent, SystemAgent, CommunicationAgent).
"""

import pytest
from jarvis.agents import (
    ResearchAgent, CodingAgent, SystemAgent, CommunicationAgent,
    RESEARCH_TOOLS, CODING_TOOLS, SYSTEM_TOOLS, COMMUNICATION_TOOLS
)
from jarvis.tools import ToolRegistry


def test_specialized_agents_tool_scopes():
    registry = ToolRegistry()

    r_agent = ResearchAgent()
    r_schemas = r_agent.get_tool_schemas(registry)
    r_names = {s["function"]["name"] for s in r_schemas}
    assert r_names.issubset(RESEARCH_TOOLS)
    assert "web_search" in r_names

    c_agent = CodingAgent()
    c_schemas = c_agent.get_tool_schemas(registry)
    c_names = {s["function"]["name"] for s in c_schemas}
    assert c_names.issubset(CODING_TOOLS)
    assert "inspect_project" in c_names

    s_agent = SystemAgent()
    s_schemas = s_agent.get_tool_schemas(registry)
    s_names = {s["function"]["name"] for s in s_schemas}
    assert s_names.issubset(SYSTEM_TOOLS)
    assert "get_system_status" in s_names

    comm_agent = CommunicationAgent()
    comm_schemas = comm_agent.get_tool_schemas(registry)
    comm_names = {s["function"]["name"] for s in comm_schemas}
    assert comm_names.issubset(COMMUNICATION_TOOLS)
    assert "send_email" in comm_names
