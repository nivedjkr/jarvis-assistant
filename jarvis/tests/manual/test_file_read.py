"""
Rigorous File Read Grounding & Exact-String Test for JARVIS
"""
import sys
import os
import asyncio
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path

root_dir = str(Path(__file__).resolve().parents[3])
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

print("Testing JARVIS Exact-String File Read Grounding & Anti-Fabrication...\n")

from jarvis.cli import JARVISCLI

cli = JARVISCLI()

file1_path = "unique_test_1.txt"
file1_content = "UNIQUE_TEST_STRING_38291_ALPHA"

file2_path = "unique_test_2.txt"
file2_content = "DIFFERENT_TEST_STRING_99482_BETA"

# Write test files to disk
with open(file1_path, "w", encoding="utf-8") as f:
    f.write(file1_content)

with open(file2_path, "w", encoding="utf-8") as f:
    f.write(file2_content)

async def run_file_read_tests():
    try:
        # Test 1: Natural Language Read File 1
        print("--- Test 1: Reading File 1 ('read unique_test_1.txt') ---")
        res1 = await cli.process_command("read unique_test_1.txt")
        print(f"✓ Output:\n{res1}\n")
        assert file1_content in res1, f"Expected exact string '{file1_content}' not found in output!"

        # Test 2: Natural Language Read File 2 (Rule out caching / hardcoding)
        print("--- Test 2: Reading File 2 ('read unique_test_2.txt') ---")
        res2 = await cli.process_command("read unique_test_2.txt")
        print(f"✓ Output:\n{res2}\n")
        assert file2_content in res2, f"Expected exact string '{file2_content}' not found in output!"

        # Test 3: Alternative Natural Language Prompt ("what is in unique_test_1.txt?")
        print("--- Test 3: Alternative Natural Language Prompt ---")
        res3 = await cli.process_command("what is in unique_test_1.txt?")
        print(f"✓ Output:\n{res3}\n")
        assert file1_content in res3, f"Expected exact string '{file1_content}' not found in output!"

        # Test 4: List Files Grounding
        print("--- Test 4: List Files Grounding ---")
        res_list = await cli.process_command("list files")
        print(f"✓ Output:\n{res_list[:300]}...\n")
        assert "unique_test_1.txt" in res_list
        assert "unique_test_2.txt" in res_list

        # Test 5: Search Files Grounding
        print("--- Test 5: Search Files Grounding ---")
        res_search = await cli.process_command("search files unique_test_*.txt")
        print(f"✓ Output:\n{res_search}\n")
        assert "unique_test_1.txt" in res_search
        assert "unique_test_2.txt" in res_search

    finally:
        # Cleanup temporary test files
        for p in [file1_path, file2_path]:
            if os.path.exists(p):
                os.remove(p)

asyncio.run(run_file_read_tests())

print("All Exact-String File Read Grounding tests PASSED successfully!")
