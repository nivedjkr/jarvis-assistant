"""
Unit & Integration Tests for Mark 5 Proactive Follow-Up Engine.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from jarvis.proactive_engine import (
    ProactiveFollowUpEngine, RelevanceGate, ValueGate,
    TaskStatus, TaskOutcome, ProactiveTask
)


# --- TEST CASE 1: Relevance Gate Filtering ---
@pytest.mark.asyncio
async def test_relevance_gate_exclusions():
    gate = RelevanceGate()

    # Routine greetings / small talk
    res1 = await gate.evaluate("hello", "Hello, sir. How can I assist you?")
    assert res1["should_investigate"] is False

    res2 = await gate.evaluate("thanks jarvis", "You are welcome, sir.")
    assert res2["should_investigate"] is False

    # Simple math calculation
    res3 = await gate.evaluate("what is 2 + 2", "2 + 2 = 4, sir.")
    assert res3["should_investigate"] is False


@pytest.mark.asyncio
async def test_relevance_gate_actionable_topic():
    gate = RelevanceGate()

    # Actionable topic / goal
    res = await gate.evaluate(
        "I'm going to work on Mark 5 this week.",
        "That sounds excellent, sir. Let me know if you need assistance."
    )
    assert res["should_investigate"] is True
    assert "Mark 5" in res["topic"]
    assert "web_search" in res["suggested_sources"]


# --- TEST CASE 2 & 3: Value Gate Filtering ---
@pytest.mark.asyncio
async def test_value_gate_redundancy_filtering():
    gate = ValueGate()

    user_prompt = "I'm going to work on Mark 5 this week."
    main_response = "Mark 5 architecture includes a proactive follow-up engine."

    # Redundant finding (already in main response)
    findings_redundant = [{"source": "web_search", "content": "Mark 5 architecture includes a proactive follow-up engine."}]
    res_redundant = await gate.evaluate(user_prompt, main_response, findings_redundant)
    assert res_redundant is None

    # Novel finding (genuinely new information)
    findings_novel = [{"source": "web_search", "content": "A lightweight task graph approach simplifies Mark 5 runtime state management."}]
    res_novel = await gate.evaluate(user_prompt, main_response, findings_novel)
    assert res_novel is not None
    assert "task graph" in res_novel


# --- TEST CASE 4: End-to-End Proactive Follow-Up Flow ---
@pytest.mark.asyncio
async def test_end_to_end_proactive_followup():
    engine = ProactiveFollowUpEngine(cooldown_seconds=0.0)

    session_id = "test_session_mark5"
    user_prompt = "I'm going to work on Mark 5 this week."
    main_response = "Understood, sir. I will stand by for your instructions."

    mock_registry = MagicMock()
    mock_registry.execute = AsyncMock(return_value="Discovered lightweight task graph pipeline for Mark 5 architecture.")

    events_emitted = []

    def event_cb(payload):
        events_emitted.append(payload)

    task = await engine.analyze_and_followup(
        session_id=session_id,
        user_prompt=user_prompt,
        main_response=main_response,
        tool_registry=mock_registry,
        llm_client=None,
        event_callback=event_cb
    )

    # Wait for background task task loop to complete
    await asyncio.sleep(0.1)

    assert task.status == TaskStatus.COMPLETED
    assert task.final_outcome == TaskOutcome.FOLLOW_UP_SENT

    # Verify emitted events sequence
    event_types = [e.get("event") for e in events_emitted]
    assert "proactive_analysis_started" in event_types
    assert "proactive_investigation_started" in event_types
    assert "proactive_result_ready" in event_types
    assert "proactive_followup_sent" in event_types

    # Find final follow-up payload
    followup_event = next(e for e in events_emitted if e.get("type") == "proactive_followup")
    assert "One more thing, sir" in followup_event["text"]
    assert "task graph" in followup_event["text"]


# --- TEST CASE 5: Session Cooldown & Rate Limiting ---
@pytest.mark.asyncio
async def test_proactive_cooldown():
    engine = ProactiveFollowUpEngine(cooldown_seconds=10.0)
    session_id = "test_session_cooldown"

    mock_registry = MagicMock()
    mock_registry.execute = AsyncMock(return_value="Discovered new info.")

    events1 = []
    # Turn 1 -> Triggers follow-up
    task1 = await engine.analyze_and_followup(
        session_id=session_id,
        user_prompt="I'm going to work on Mark 5 this week.",
        main_response="Understood, sir.",
        tool_registry=mock_registry,
        llm_client=None,
        event_callback=lambda e: events1.append(e)
    )
    await asyncio.sleep(0.1)
    assert task1.final_outcome == TaskOutcome.FOLLOW_UP_SENT

    events2 = []
    # Turn 2 -> Immediate prompt during cooldown -> No action
    task2 = await engine.analyze_and_followup(
        session_id=session_id,
        user_prompt="I'm also building a new plugin for Mark 5.",
        main_response="Noted, sir.",
        tool_registry=mock_registry,
        llm_client=None,
        event_callback=lambda e: events2.append(e)
    )
    await asyncio.sleep(0.1)
    assert task2.final_outcome == TaskOutcome.NO_ACTION
    no_action_event = next((e for e in events2 if e.get("event") == "proactive_no_action"), None)
    assert no_action_event is not None
    assert "cooldown" in no_action_event["reason"].lower()


# --- TEST CASE 6: Error Handling & Robustness ---
@pytest.mark.asyncio
async def test_proactive_error_handling():
    engine = ProactiveFollowUpEngine(cooldown_seconds=0.0)
    session_id = "test_session_err"

    mock_registry = MagicMock()
    mock_registry.execute = AsyncMock(side_effect=RuntimeError("Search API timeout"))

    events = []
    task = await engine.analyze_and_followup(
        session_id=session_id,
        user_prompt="I'm going to work on Mark 5 this week.",
        main_response="Understood, sir.",
        tool_registry=mock_registry,
        llm_client=None,
        event_callback=lambda e: events.append(e)
    )
    await asyncio.sleep(0.1)

    assert task.status == TaskStatus.COMPLETED
    assert task.final_outcome == TaskOutcome.NO_ACTION
