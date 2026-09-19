---
name: subagent-orchestrator
description: Coordinate multi-agent swarms and delegating complex subtasks across specialized agents (CodingAgent, ResearchAgent, SystemAgent, CommunicationAgent). Activate when facing multi-phase goals requiring parallel or specialized execution.
category: orchestration
---

# Subagent Orchestration & Swarm Coordination

Decomposing high-level goals into isolated tasks executed by dedicated agent roles prevents context saturation and maximizes domain specialization.

## Available Agent Roles

1. **PlanningAgent**:
   - Decomposes high-level prompts into actionable subtasks with explicit dependencies.
2. **CodingAgent**:
   - Software development, unit testing, debugging, Git operations, and syntax verification.
3. **ResearchAgent**:
   - Web search, web scraping, documentation indexing, and Obsidian memory querying.
4. **SystemAgent**:
   - Local OS automation, process management, diagnostics, and environment configuration.
5. **CommunicationAgent**:
   - Email dispatch, Google Calendar events, and user briefing synthesis.

## Swarm Workflow

1. Use `invoke_subagent` specifying the target role (`CodingAgent`, `ResearchAgent`, etc.) and a self-contained task prompt.
2. Use `list_subagents` to monitor execution status and outputs.
3. Synthesize individual subagent results into the unified response for the user.
