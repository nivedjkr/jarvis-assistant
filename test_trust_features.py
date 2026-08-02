"""
Automated Ground-Truth Verification for Trust & Transparency Features
"""
import sys
import os
import asyncio
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Testing Trust & Transparency Features...\n")

from jarvis.cli import JARVISCLI

cli = JARVISCLI()

async def run_trust_tests():
    # -------------------------------------------------------------
    # 1. Self-Diagnostic Mode (/diagnose)
    # -------------------------------------------------------------
    print("--- 1. Self-Diagnostic Mode (/diagnose) ---")
    diag_res = await cli.process_command("/diagnose")
    print(f"✓ Output:\n{diag_res}\n")
    assert "Self-diagnostic check complete" in diag_res

    # -------------------------------------------------------------
    # 2. Confidence-Flagged Responses
    # -------------------------------------------------------------
    print("--- 2. Confidence-Flagged Responses ---")
    # Test fuzzy app match warning (single fuzzy match)
    app_res = await cli.process_command("open chroome")
    print(f"✓ Fuzzy App Match Output:\n{app_res}\n")
    assert "[CONFIDENCE WARNING]" in app_res
    assert "chrome" in app_res

    # Test file path resolution warning
    notes_file = "test_path_resolve.txt"
    with open(notes_file, "w", encoding="utf-8") as f:
        f.write("Test content for path resolution")
    try:
        path_res = await cli.process_command(f"read {notes_file}")
        print(f"✓ File Path Resolution Output:\n{path_res}\n")
        assert "[PATH RESOLUTION]" in path_res
    finally:
        if os.path.exists(notes_file):
            os.remove(notes_file)

    # -------------------------------------------------------------
    # 3. Action Explanation Command (/why & /why <n>)
    # -------------------------------------------------------------
    print("--- 3. Action Explanation (/why & /why <n>) ---")
    # Run a tool command first
    git_res = await cli.process_command("what's my git status")
    print(f"Executed Tool Command: {git_res[:100]}...\n")

    # Inspect with /why
    why_res = await cli.process_command("/why")
    print(f"✓ /why Output:\n{why_res}\n")
    assert "git_status" in why_res or "Displayed action explanation" in why_res

    # Inspect with /why 1
    why1_res = await cli.process_command("/why 1")
    print(f"✓ /why 1 Output:\n{why1_res}\n")
    assert "git_status" in why1_res or "Displayed action explanation" in why1_res

    # Test conversational response (no tool)
    cli.tools.last_transactions = []  # Clear transactions
    why_no_tool = await cli.process_command("/why")
    print(f"✓ /why (no tools used) Output:\n{why_no_tool}\n")
    assert "no tools were used" in why_no_tool.lower()

    # -------------------------------------------------------------
    # 4. Help Command Category (/help diagnostics)
    # -------------------------------------------------------------
    print("--- 4. Help Command (/help diagnostics) ---")
    help_diag_res = await cli.process_command("/help diagnostics")
    print(f"✓ /help diagnostics Output:\n{help_diag_res}\n")
    assert "diagnostics" in help_diag_res.lower()

asyncio.run(run_trust_tests())

print("All Trust & Transparency Features tests PASSED successfully!")
