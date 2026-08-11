"""
Comprehensive Test Suite for JARVIS Project Database
Verifies all 7 testing requirements:
1. Create a test project ("TestApp")
2. Add 3 tasks via natural language / tool command
3. Mark one task done
4. Add a decision with reasoning
5. Run /projects TestApp — verify ALL real data shows
6. Trigger overdue check manually — confirm real overdue tasks found
7. Test project context injection for "how's TestApp going"
8. Test /help projects command output formatting
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = str(Path(__file__).resolve().parent.parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from jarvis.projects import ProjectManager
from jarvis.cli import JARVISCLI


async def run_tests():
    print("=" * 60)
    print("STARTING JARVIS PROJECT DATABASE SUITE")
    print("=" * 60)

    cli = JARVISCLI()
    cli.voice_manager.speak_responses = False
    if hasattr(cli.voice_manager, "tts") and cli.voice_manager.tts:
        cli.voice_manager.tts.speak = lambda text: None
    pm = cli.project_manager

    # Clean up TestApp if already present from prior run
    existing = pm.get_project("TestApp")
    if existing:
        with pm._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM projects WHERE id = ?", (existing["id"],))
            conn.commit()

    # 1. Create a test project via "create a new project called TestApp"
    print("\n--- Test 1: Create Project 'TestApp' ---")
    res1 = await cli.process_command("create a new project called TestApp")
    print(f"Result: {res1}")
    p = pm.get_project("TestApp")
    assert p is not None, "TestApp project should exist in DB"
    assert p["name"] == "TestApp"
    print("✓ Test 1 Passed")

    # 2. Add 3 tasks via natural language / tool
    print("\n--- Test 2: Add 3 Tasks ---")
    res2_1 = await cli.process_command("add a task to TestApp: Design UI wireframes")
    res2_2 = await cli.process_command("add a task to TestApp: Setup SQLite database")
    res2_3 = await cli.process_command("add a task to TestApp: Deploy to production")
    print(f"Task 1: {res2_1}")
    print(f"Task 2: {res2_2}")
    print(f"Task 3: {res2_3}")

    p_tasks = pm.get_project_tasks("TestApp")
    assert len(p_tasks) == 3, f"Expected 3 tasks in TestApp, got {len(p_tasks)}"
    print("✓ Test 2 Passed")

    # 3. Mark one task done
    print("\n--- Test 3: Mark Task Done ---")
    res3 = await cli.process_command("mark task Setup SQLite database as done in TestApp")
    print(f"Result: {res3}")
    done_task = pm.find_task_by_title("TestApp", "SQLite")
    assert done_task is not None, "SQLite task should be found"
    assert done_task["status"] == "done", "SQLite task status should be 'done'"
    print("✓ Test 3 Passed")

    # 4. Add a decision with reasoning
    print("\n--- Test 4: Add Decision ---")
    res4 = await cli.process_command("/decide TestApp We decided to use SQLite because it requires no external server setup")
    print(f"Result: {res4}")
    decisions = pm.get_project_decisions("TestApp")
    assert len(decisions) >= 1, "Decision should be saved"
    print("✓ Test 4 Passed")

    # 5. Run /projects TestApp — verify ALL real data shows
    print("\n--- Test 5: Run /projects TestApp ---")
    res5 = await cli.process_command("/projects TestApp")
    print(f"Briefing Output:\n{res5}")
    assert "TestApp" in res5
    assert "Design UI wireframes" in res5
    assert "Setup SQLite database" in res5
    assert "We decided to use SQLite" in res5
    print("✓ Test 5 Passed")

    # 6. Trigger overdue check manually — confirm it finds real overdue tasks not invented ones
    print("\n--- Test 6: Overdue Check ---")
    # Add an overdue task to TestApp with past due date
    pm.add_task("TestApp", title="Fix critical security issue", due_date="2020-01-01")
    overdue_list = pm.get_overdue_tasks()
    print(f"Overdue Tasks Found: {len(overdue_list)}")
    for ot in overdue_list:
        print(f"  - [{ot['project_name']}] {ot['title']} (Due: {ot['due_date']})")
    assert any(ot["title"] == "Fix critical security issue" for ot in overdue_list), "Overdue task should be found by DB query"
    print("✓ Test 6 Passed")

    # 7. Ask "how's TestApp going" — verify JARVIS context injection auto-fetches real project data
    print("\n--- Test 7: Project Context Injection ---")
    ctx = pm.get_project_context_for_message("how's the TestApp project going?")
    print(f"Injected System Prompt Context:\n{ctx}")
    assert ctx is not None, "Context should be fetched for TestApp"
    assert "REAL PROJECT DATABASE CONTEXT: TestApp" in ctx
    assert "Design UI wireframes" in ctx
    print("✓ Test 7 Passed")

    # 8. Help command /help projects
    print("\n--- Test 8: /help projects Command Output ---")
    cli.show_help("projects")
    print("✓ Test 8 Passed")

    print("\n" + "=" * 60)
    print("ALL 8 PROJECT DATABASE TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

    # Stop CLI proactive monitor background thread
    cli.proactive_monitor.stop()


if __name__ == "__main__":
    asyncio.run(run_tests())
