"""
Test multi-instruction splitting and execution in JARVIS CLI
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

print("Testing JARVIS Multi-Instruction functionality...\n")

from jarvis.cli import JARVISCLI

cli = JARVISCLI()

# Test 1: Instruction Splitting
test_cases = [
    ("open notepad and create a folder called test_dir", 2),
    ("open youtube, remind me to call mom, and note: test note", 3),
    ("read file config.yaml then list files in .", 2),
    ("search web for cats and dogs", 1), # Should NOT split query
    ("open chrome; open vscode\nremind me to check emails", 3)
]

print("--- Test 1: Instruction Splitting ---")
all_split_passed = True
for query, expected_count in test_cases:
    splits = cli._split_instructions(query)
    status = "✓" if len(splits) == expected_count else "✗"
    if len(splits) != expected_count:
        all_split_passed = False
    print(f"{status} Input: '{query}'")
    print(f"   Splits ({len(splits)}): {splits}")

if all_split_passed:
    print("\n✓ All instruction splitting tests PASSED!\n")
else:
    print("\n✗ Some instruction splitting tests failed.\n")


# Test 2: Execution of Compound Tool Commands
async def test_execution():
    print("--- Test 2: Compound Command Execution ---")
    compound_prompt = "remind me to complete testing and note: multi instruction test passed"
    print(f"Executing: '{compound_prompt}'")
    result = await cli.process_command(compound_prompt)
    print(f"Result:\n{result}\n")
    
    assert "Reminder added" in result and "Note saved" in result
    print("✓ Compound command execution test PASSED!")

asyncio.run(test_execution())
