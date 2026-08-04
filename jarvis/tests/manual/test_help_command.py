"""
Automated Test for Categorized /help Command & Category Filtering
"""
import sys
import asyncio
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Testing Categorized /help Command & Category Filtering...\n")

from jarvis.cli import JARVISCLI

cli = JARVISCLI()

async def run_help_tests():
    # Test 1: Full Categorized /help Command
    print("--- Test 1: Full Categorized /help Command ---")
    res1 = await cli.process_command("/help")
    print(f"✓ Output summary:\n{res1}\n")
    assert "help information" in res1.lower()

    # Test 2: Category Filtered /help trading
    print("--- Test 2: Filtered /help trading ---")
    res2 = await cli.process_command("/help trading")
    print(f"✓ Output summary:\n{res2}\n")
    assert "trading" in res2.lower()

    # Test 3: Category Filtered /help study
    print("--- Test 3: Filtered /help study ---")
    res3 = await cli.process_command("/help study")
    print(f"✓ Output summary:\n{res3}\n")
    assert "study" in res3.lower()

    # Test 4: /whoami Command
    print("--- Test 4: /whoami Command ---")
    res4 = await cli.process_command("/whoami")
    print(f"✓ Output:\n{res4}\n")
    assert "user profile" in res4.lower()

asyncio.run(run_help_tests())

print("All /help Command tests PASSED successfully!")
