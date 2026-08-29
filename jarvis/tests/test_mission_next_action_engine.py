"""
Unit Tests for J.A.R.V.I.S. Mk 5.2.0 — Persistent Mission Next Action Engine
Tests deterministic next-task selection, dependency resolution, blocker handling,
priority ordering, inactive state handling, and output contract consistency.
"""

import pytest
import time
from jarvis.mission_manager import (
    MissionManager, NextActionEngine, MissionStatus, MissionTaskStatus, NextActionResult
)


@pytest.fixture
def temp_db_path(tmp_path):
    return str(tmp_path / "test_next_action_engine.db")


# --- TEST 1: SINGLE ACTIONABLE TASK ---
def test_single_actionable_task(temp_db_path):
    manager = MissionManager(db_path=temp_db_path)
    mission = manager.propose_mission("Test Goal", "Achieve single task goal.")
    manager.update_mission_status(mission.id, MissionStatus.ACTIVE)

    task = manager.create_task(mission.id, "Task A", "Initial task description")
    manager.update_task_status(task.id, MissionTaskStatus.READY)

    result = manager.get_next_actionable_task(mission.id)

    assert isinstance(result, NextActionResult)
    assert result.actionable is True
    assert result.task_id == task.id
    assert result.task_title == "Task A"
    assert result.reason == "NEXT_TASK_SELECTED"
    assert result.dependencies_satisfied is True
    assert result.blocked is False


# --- TEST 2: COMPLETED TASKS IGNORED ---
def test_completed_tasks_ignored(temp_db_path):
    manager = MissionManager(db_path=temp_db_path)
    mission = manager.propose_mission("Test Goal", "Multi-task progression.")
    manager.update_mission_status(mission.id, MissionStatus.ACTIVE)

    task_a = manager.create_task(mission.id, "Task A", "First step")
    task_b = manager.create_task(mission.id, "Task B", "Second step")

    # Complete Task A
    manager.update_task_status(task_a.id, MissionTaskStatus.RUNNING)
    manager.update_task_status(task_a.id, MissionTaskStatus.COMPLETED, result="Done step A")

    manager.update_task_status(task_b.id, MissionTaskStatus.READY)

    result = manager.get_next_actionable_task(mission.id)

    assert result.actionable is True
    assert result.task_id == task_b.id
    assert result.task_title == "Task B"


# --- TEST 3: DEPENDENCY BLOCKING ---
def test_dependency_blocking(temp_db_path):
    manager = MissionManager(db_path=temp_db_path)
    mission = manager.propose_mission("Test Goal", "Dependency chain.")
    manager.update_mission_status(mission.id, MissionStatus.ACTIVE)

    task_a = manager.create_task(mission.id, "Task A", "First step")
    task_b = manager.create_task(mission.id, "Task B", "Second step depends on A", depends_on=[task_a.id])

    # Mark Task A as WAITING (blocked) so Task A itself is not actionable
    manager.update_task_status(task_a.id, MissionTaskStatus.READY)
    manager.update_task_status(task_a.id, MissionTaskStatus.WAITING)
    manager.update_task_status(task_b.id, MissionTaskStatus.READY)

    result = manager.get_next_actionable_task(mission.id)

    assert result.actionable is False
    assert result.task is None
    assert result.reason in ("WAITING_ON_DEPENDENCIES", "ALL_TASKS_BLOCKED")


# --- TEST 4: DEPENDENCY COMPLETED ---
def test_dependency_completed(temp_db_path):
    manager = MissionManager(db_path=temp_db_path)
    mission = manager.propose_mission("Test Goal", "Dependency resolution.")
    manager.update_mission_status(mission.id, MissionStatus.ACTIVE)

    task_a = manager.create_task(mission.id, "Task A", "Prerequisite step")
    task_b = manager.create_task(mission.id, "Task B", "Dependent step", depends_on=[task_a.id])

    # Complete prerequisite Task A
    manager.update_task_status(task_a.id, MissionTaskStatus.RUNNING)
    manager.update_task_status(task_a.id, MissionTaskStatus.COMPLETED, result="Prerequisite complete")
    manager.update_task_status(task_b.id, MissionTaskStatus.READY)

    result = manager.get_next_actionable_task(mission.id)

    assert result.actionable is True
    assert result.task_id == task_b.id
    assert result.dependencies_satisfied is True


# --- TEST 5: PRIORITY ORDERING ---
def test_priority_ordering(temp_db_path):
    manager = MissionManager(db_path=temp_db_path)
    mission = manager.propose_mission("Test Goal", "Priority resolution.")
    manager.update_mission_status(mission.id, MissionStatus.ACTIVE)

    task_a = manager.create_task(mission.id, "Task A (P1)", priority="1")
    task_b = manager.create_task(mission.id, "Task B (P5)", priority="5")
    task_c = manager.create_task(mission.id, "Task C (P3)", priority="3")

    result = manager.get_next_actionable_task(mission.id)

    assert result.actionable is True
    assert result.task_id == task_b.id
    assert result.task_title == "Task B (P5)"
    assert result.priority == "5"


# --- TEST 6: INACTIVE MISSION ---
def test_inactive_mission(temp_db_path):
    manager = MissionManager(db_path=temp_db_path)
    mission = manager.propose_mission("Test Goal", "Inactive mission check.")
    manager.update_mission_status(mission.id, MissionStatus.ACTIVE)

    task = manager.create_task(mission.id, "Task A", priority="HIGH")

    # Pause mission
    manager.pause_mission(mission.id)

    result = manager.get_next_actionable_task(mission.id)

    assert result.actionable is False
    assert result.task is None
    assert result.reason == "MISSION_NOT_ACTIVE"


# --- TEST 7: ALL TASKS COMPLETED ---
def test_all_tasks_completed(temp_db_path):
    manager = MissionManager(db_path=temp_db_path)
    mission = manager.propose_mission("Test Goal", "Completion check.")
    manager.update_mission_status(mission.id, MissionStatus.ACTIVE)

    task_a = manager.create_task(mission.id, "Task A")
    task_b = manager.create_task(mission.id, "Task B")

    manager.update_task_status(task_a.id, MissionTaskStatus.RUNNING)
    manager.update_task_status(task_a.id, MissionTaskStatus.COMPLETED)
    manager.update_task_status(task_b.id, MissionTaskStatus.RUNNING)
    manager.update_task_status(task_b.id, MissionTaskStatus.COMPLETED)

    result = manager.get_next_actionable_task(mission.id)

    assert result.actionable is False
    assert result.task is None
    assert result.reason == "ALL_TASKS_COMPLETED"


# --- TEST 8: ALL TASKS BLOCKED ---
def test_all_tasks_blocked(temp_db_path):
    manager = MissionManager(db_path=temp_db_path)
    mission = manager.propose_mission("Test Goal", "Blocked check.")
    manager.update_mission_status(mission.id, MissionStatus.ACTIVE)

    task_a = manager.create_task(mission.id, "Task A")
    manager.update_task_status(task_a.id, MissionTaskStatus.READY)
    manager.update_task_status(task_a.id, MissionTaskStatus.WAITING)

    result = manager.get_next_actionable_task(mission.id)

    assert result.actionable is False
    assert result.task is None
    assert result.reason in ("ALL_TASKS_BLOCKED", "WAITING_ON_DEPENDENCIES")


# --- TEST 9: DETERMINISTIC SELECTION ---
def test_deterministic_selection(temp_db_path):
    manager = MissionManager(db_path=temp_db_path)
    engine = NextActionEngine(manager)

    mission = manager.propose_mission("Test Goal", "Determinism check.")
    manager.update_mission_status(mission.id, MissionStatus.ACTIVE)

    t1 = manager.create_task(mission.id, "Task 1", priority="MEDIUM")
    t2 = manager.create_task(mission.id, "Task 2", priority="MEDIUM")
    t3 = manager.create_task(mission.id, "Task 3", priority="MEDIUM")

    first_result = engine.get_next_actionable_task(mission.id)
    assert first_result.actionable is True

    # Evaluate 10 times in sequence
    for _ in range(10):
        subsequent_result = engine.get_next_actionable_task(mission.id)
        assert subsequent_result.actionable is True
        assert subsequent_result.task_id == first_result.task_id
        assert subsequent_result.task_title == first_result.task_title


# --- TEST 10: TOOL REGISTRY FIRST-CLASS IN-PROCESS TOOL ---
def test_next_action_tool_registry_integration(temp_db_path):
    import json
    from jarvis.tools import ToolRegistry
    manager = MissionManager(db_path=temp_db_path)
    registry = ToolRegistry(mission_manager=manager)

    assert "get_next_actionable_task" in registry.tools

    mission = manager.propose_mission("Tool Goal", "Test direct tool invocation.")
    manager.update_mission_status(mission.id, MissionStatus.ACTIVE)
    task = manager.create_task(mission.id, "Tool Task", priority="HIGH")
    manager.update_task_status(task.id, MissionTaskStatus.READY)

    output_str = registry.execute_tool("get_next_actionable_task", {"mission_id": mission.id})
    data = json.loads(output_str)

    assert data["actionable"] is True
    assert data["mission_id"] == mission.id
    assert data["task_id"] == task.id
    assert data["task_title"] == "Tool Task"
    assert data["reason"] == "NEXT_TASK_SELECTED"
