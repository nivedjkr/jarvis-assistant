"""
Unit & Integration Tests for Mark 5 Persistent Mission Intelligence.
"""

import pytest
import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

from jarvis.mission_manager import (
    MissionManager, MissionDetector, MissionStatus, MissionTaskStatus,
    validate_mission_transition, validate_task_transition
)
from jarvis.proactive_engine import ProactiveFollowUpEngine, TaskStatus, TaskOutcome


@pytest.fixture
def temp_db_path(tmp_path):
    return str(tmp_path / "test_jarvis.db")


# --- TEST 1: Casual Conversation Creates No Mission ---
@pytest.mark.asyncio
async def test_casual_conversation_creates_no_mission():
    detector = MissionDetector()

    res1 = await detector.evaluate("hello jarvis")
    assert res1["should_propose_mission"] is False

    res2 = await detector.evaluate("what is 2 + 2")
    assert res2["should_propose_mission"] is False

    res3 = await detector.evaluate("thanks for your help")
    assert res3["should_propose_mission"] is False


# --- TEST 2: Long-Term Objective Produces Mission Proposal ---
@pytest.mark.asyncio
async def test_long_term_objective_proposes_mission(temp_db_path):
    manager = MissionManager(db_path=temp_db_path)
    detector = MissionDetector()

    user_prompt = "I want to find a good internship this year."
    res = await detector.evaluate(user_prompt)

    assert res["should_propose_mission"] is True
    assert "internship" in res["title"].lower()

    # Create proposed mission
    mission = manager.propose_mission(
        title=res["title"],
        objective=res["objective"],
        description=res["reason"],
        source_conversation_id="session_123"
    )

    assert mission.status == MissionStatus.PROPOSED
    assert mission.id.startswith("mission_")


# --- TEST 3: User Rejects Proposal -> Cancelled (No Active Mission Stored) ---
@pytest.mark.asyncio
async def test_user_rejects_mission_proposal(temp_db_path):
    manager = MissionManager(db_path=temp_db_path)

    mission = manager.propose_mission(
        title="Find an internship",
        objective="Secure an internship this year."
    )
    assert mission.status == MissionStatus.PROPOSED

    # Reject / Cancel
    cancelled_m = manager.cancel_mission(mission.id)
    assert cancelled_m.status == MissionStatus.CANCELLED

    # Verify no ACTIVE mission exists
    active_list = manager.list_missions(status=MissionStatus.ACTIVE)
    assert len(active_list) == 0


# --- TEST 4 & 5: User Approves -> Mission Persists & Creates Tasks ---
@pytest.mark.asyncio
async def test_user_approves_mission_persistence_and_tasks(temp_db_path):
    manager1 = MissionManager(db_path=temp_db_path)

    mission = manager1.propose_mission(
        title="Find and secure a suitable internship",
        objective="Find and secure a software engineering internship position this year."
    )

    # Approve mission
    activated_m = manager1.approve_mission(mission.id)
    assert activated_m.status in (MissionStatus.EXECUTING, MissionStatus.PLANNING, MissionStatus.ACTIVE)
    assert len(activated_m.tasks) >= 3

    # Re-instantiate Manager (simulate app/server restart)
    manager2 = MissionManager(db_path=temp_db_path)
    reloaded_m = manager2.get_mission(mission.id)

    assert reloaded_m is not None
    assert reloaded_m.title == "Find and secure a suitable internship"
    assert len(reloaded_m.tasks) == len(activated_m.tasks)


# --- TEST 6: Task Completion Updates Mission Progress ---
@pytest.mark.asyncio
async def test_task_completion_updates_progress(temp_db_path):
    manager = MissionManager(db_path=temp_db_path)

    m = manager.propose_mission("Test Mission", "Complete all milestone tasks.")
    m = manager.approve_mission(m.id)

    assert m.progress_percentage == 0.0
    task1 = m.tasks[0]

    # Start task -> RUNNING -> COMPLETED
    manager.update_task_status(task1.id, MissionTaskStatus.RUNNING)
    manager.update_task_status(task1.id, MissionTaskStatus.COMPLETED, result="Finished step 1")

    updated_m = manager.get_mission(m.id)
    assert updated_m.progress_percentage > 0.0
    assert updated_m.completed_task_count == 1


# --- TEST 7: Failed Task Handling ---
@pytest.mark.asyncio
async def test_failed_task_recorded_correctly(temp_db_path):
    manager = MissionManager(db_path=temp_db_path)

    m = manager.propose_mission("Failure Test Mission", "Objective with task failure.")
    m = manager.approve_mission(m.id)

    task1 = m.tasks[0]
    manager.update_task_status(task1.id, MissionTaskStatus.RUNNING)
    manager.update_task_status(task1.id, MissionTaskStatus.FAILED, error="Connection timeout")

    updated_task = manager.get_task(task1.id)
    assert updated_task.status == MissionTaskStatus.FAILED
    assert updated_task.error == "Connection timeout"

    updated_m = manager.get_mission(m.id)
    assert updated_m.status == MissionStatus.FAILED


# --- TEST 8: State Machine Guarantees (No Invalid / Stuck Transitions) ---
def test_state_machine_transitions():
    # Invalid mission transition
    with pytest.raises(ValueError):
        validate_mission_transition(MissionStatus.PROPOSED, MissionStatus.EXECUTING)

    # Invalid task transition
    with pytest.raises(ValueError):
        validate_task_transition(MissionTaskStatus.PENDING, MissionTaskStatus.COMPLETED)

    # Valid transitions
    validate_mission_transition(MissionStatus.PROPOSED, MissionStatus.ACTIVE)
    validate_mission_transition(MissionStatus.ACTIVE, MissionStatus.PAUSED)
    validate_task_transition(MissionTaskStatus.PENDING, MissionTaskStatus.RUNNING)
    validate_task_transition(MissionTaskStatus.RUNNING, MissionTaskStatus.COMPLETED)


# --- TEST 9: Desktop & Mobile Receive Mission Events ---
@pytest.mark.asyncio
async def test_desktop_mobile_receive_mission_events(temp_db_path):
    engine = ProactiveFollowUpEngine(cooldown_seconds=0.0, db_path=temp_db_path)

    session_id = "test_session_events"
    user_prompt = "I want to find a good internship this year."
    main_response = "I can certainly help you plan that, sir."

    mock_registry = MagicMock()
    mock_registry.execute = AsyncMock(return_value="Discovered internship resources.")

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

    await asyncio.sleep(0.1)

    mission_events = [e for e in events_emitted if e.get("type") == "mission_event"]
    assert len(mission_events) > 0
    assert mission_events[0]["event"] == "mission_proposed"
    assert "internship" in mission_events[0]["mission"]["title"].lower()
