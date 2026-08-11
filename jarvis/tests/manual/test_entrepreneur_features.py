"""
Automated Ground-Truth Verification for Entrepreneur Features Phase 3
"""
import sys
import asyncio
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import os
from pathlib import Path

root_dir = str(Path(__file__).resolve().parents[3])
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

print("Testing Entrepreneur Features (Phase 3)...\n")

from jarvis.cli import JARVISCLI

cli = JARVISCLI()

async def run_entrepreneur_tests():
    # -------------------------------------------------------------
    # 1. Idea / Decision Journal
    # -------------------------------------------------------------
    print("--- 3.1 Idea Journal: Log, List, & Search ---")
    log_res = await cli.process_command("/idea Launch subscription tier for power users")
    print(f"✓ Output:\n{log_res}\n")
    assert "Idea logged" in log_res

    list_res = await cli.process_command("/ideas list")
    print(f"✓ Output:\n{list_res}\n")
    assert "Launch subscription tier" in list_res or "logged ideas" in list_res

    search_res = await cli.process_command("/ideas search subscription")
    print(f"✓ Search Output:\n{search_res}\n")
    assert "subscription" in search_res.lower()

    # -------------------------------------------------------------
    # 2. Meeting Prep
    # -------------------------------------------------------------
    print("--- 3.2 Meeting Prep Tool ---")
    cli.memory.add_fact("contacts", "Alice is the Lead Architect for Cloud Services")
    cli.memory.add_note("Discuss latency SLA targets with Alice in upcoming meeting")

    prep_res = await cli.process_command("/meeting prep Alice")
    print(f"✓ Meeting Prep Briefing Output:\n{prep_res}\n")
    assert "Alice" in prep_res
    assert "Architect" in prep_res or "SLA" in prep_res or "Cloud" in prep_res

asyncio.run(run_entrepreneur_tests())

print("All Entrepreneur Features (Phase 3) tests PASSED successfully!")
