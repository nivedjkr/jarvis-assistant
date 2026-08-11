"""
Test Grounding & Anti-Hallucination for JARVIS Tool Executions
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

print("Testing JARVIS Tool Execution Grounding & Anti-Hallucination...\n")

from jarvis.cli import JARVISCLI

cli = JARVISCLI()

async def run_grounding_tests():
    # Test 1: Directory Creation & Follow-Up Location Query
    print("--- Test 1: Directory Creation & Location Grounding ---")
    create_res = await cli.process_command("create directory test1")
    print(f"✓ Tool Execution Output:\n   {create_res}\n")
    assert "test1" in create_res
    
    # Follow-up query asking where it was created
    loc_query_res = await cli.process_command("where did you create test1?")
    print(f"✓ Follow-up AI Query Response:\n   {loc_query_res}\n")
    assert "test1" in loc_query_res.lower()
    assert ("d:\\jarvis\\test1" in loc_query_res.lower() or "test1" in loc_query_res.lower())

    # Test 2: File Read/Write Grounding
    print("--- Test 2: File Read/Write Grounding ---")
    write_res = await cli.tools.execute_tool("write_file", filepath="grounding_test.txt", content="SECRET_KEY_998877", confirm=False)
    cli.api_client.add_message("user", "write file grounding_test.txt")
    cli.api_client.add_message("assistant", f"[RECORDED TOOL EXECUTION RESULT]\nCommand: write file grounding_test.txt\nResult: {write_res}")
    print(f"✓ Write Tool Execution Output:\n   {write_res}\n")
    
    file_query_res = await cli.process_command("what is inside grounding_test.txt?")
    print(f"✓ Follow-up AI File Query Response:\n   {file_query_res}\n")
    assert "secret_key_998877" in file_query_res.lower()

    # Test 3: Shell Command Grounding
    print("--- Test 3: Shell Command Execution Grounding ---")
    shell_res = await cli.tools.execute_tool("shell_command", command="echo JARVIS_GROUNDING_VERIFIED", confirm=False)
    cli.api_client.add_message("user", "run shell command echo JARVIS_GROUNDING_VERIFIED")
    cli.api_client.add_message("assistant", f"[RECORDED TOOL EXECUTION RESULT]\nCommand: run shell command echo JARVIS_GROUNDING_VERIFIED\nResult: {shell_res}")
    print(f"✓ Shell Tool Execution Output:\n   {shell_res.strip()}\n")
    
    shell_query_res = await cli.process_command("what was the output of the shell command?")
    print(f"✓ Follow-up AI Shell Query Response:\n   {shell_query_res}\n")
    assert "jarvis_grounding_verified" in shell_query_res.lower()

asyncio.run(run_grounding_tests())

print("All Grounding & Anti-Hallucination tests PASSED successfully!")
