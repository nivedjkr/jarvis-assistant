"""
Test Real Scheduled Background Reminders System for JARVIS
"""
import sys
import asyncio
import time
from datetime import datetime, timedelta
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Testing JARVIS Real Scheduled Background Reminders System...\n")

from jarvis.cli import JARVISCLI

cli = JARVISCLI()
pm = cli.proactive_monitor
pm.check_interval = 1  # 1-second interval for test execution

async def run_reminder_tests():
    # Test 1: Natural Language Time Parsing & Creation
    print("--- Test 1: Natural Language Time Parsing ---")
    user_prompt = "remind me in 2 seconds to check the pizza"
    
    text, due_at = cli.parse_reminder_time(user_prompt)
    print(f"✓ Parsed text: '{text}'")
    print(f"✓ Parsed due_at: {due_at.strftime('%H:%M:%S')}")
    assert text == "check the pizza"
    assert (due_at - datetime.now()).total_seconds() > 0

    # Insert into database
    reminder = cli.memory.add_reminder(text, due_date=due_at.isoformat())
    print(f"✓ Inserted into SQLite DB (ID: {reminder['id']}, Status: pending)")
    
    # Test 2: Mid-Wait Query (Real DB Facts)
    print("\n--- Test 2: Mid-Wait Query (Real DB Facts) ---")
    summary = cli.get_pending_reminders_summary()
    print(f"✓ Mid-Wait Summary Output:\n{summary}\n")
    assert "check the pizza" in summary

    # Test 3: Unprompted Background Monitor Trigger
    print("--- Test 3: Automatic Unprompted Background Monitor Trigger ---")
    print("Waiting 4 seconds for background ProactiveMonitor loop (NO user input)...")
    
    # Start monitor thread
    pm.start()
    await asyncio.sleep(4)
    pm.stop()

    # Check that reminder is completed in DB
    reminders = cli.memory.get_reminders()
    completed = [r for r in reminders if r["id"] == reminder["id"] and r["completed"]]
    print(f"✓ DB Reminder status after trigger: {completed[0]['status'] if completed else 'not completed'}")
    assert len(completed) > 0

asyncio.run(run_reminder_tests())

print("\nAll Scheduled Reminders System tests PASSED successfully!")
