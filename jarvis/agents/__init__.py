"""
JARVIS Mk4 Agent Package
Contains BaseAgent and specialized logical agent roles.
"""

from jarvis.agents.base_agent import BaseAgent, AgentResponse
from jarvis.agents.research_agent import ResearchAgent, RESEARCH_TOOLS
from jarvis.agents.coding_agent import CodingAgent, CODING_TOOLS
from jarvis.agents.system_agent import SystemAgent, SYSTEM_TOOLS
from jarvis.agents.communication_agent import CommunicationAgent, COMMUNICATION_TOOLS

__all__ = [
    "BaseAgent",
    "AgentResponse",
    "ResearchAgent",
    "RESEARCH_TOOLS",
    "CodingAgent",
    "CODING_TOOLS",
    "SystemAgent",
    "SYSTEM_TOOLS",
    "CommunicationAgent",
    "COMMUNICATION_TOOLS",
]
