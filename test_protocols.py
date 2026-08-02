"""
Test Protocol Macro System for JARVIS
"""
import sys
import asyncio
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Testing JARVIS Protocol Macro System...\n")

from jarvis.cli import JARVISCLI
from jarvis.protocols import ProtocolManager

cli = JARVISCLI()
pm = cli.protocol_manager

# Test 1: Protocols Listing & Defaults
print("--- Test 1: Protocols Listing & Defaults ---")
protocols = pm.list_protocols()
proto_names = [p["name"] for p in protocols]
print(f"✓ Default protocols loaded: {proto_names}")

assert "work mode" in proto_names
assert "shutdown" in proto_names
assert "backup" in proto_names

# Test 2: Safety Checks
print("\n--- Test 2: Safety Checks ---")
work_mode_proto = pm.get_protocol("work mode")
backup_proto = pm.get_protocol("backup")

is_wm_dangerous = pm.is_dangerous(work_mode_proto)
is_bk_dangerous = pm.is_dangerous(backup_proto)

print(f"✓ 'work mode' safety check dangerous: {is_wm_dangerous}")
print(f"✓ 'backup' safety check dangerous: {is_bk_dangerous}")

assert is_bk_dangerous is True  # Backup uses shell command make_archive

# Test 3: Natural Language Triggers
print("\n--- Test 3: Natural Language Triggers ---")
async def test_triggers():
    # Test work mode execution with confirm=False
    res_wm = await pm.execute_protocol("work mode", tools=cli.tools, confirm=False)
    print(f"✓ Work mode execution output:\n{res_wm}\n")
    assert "Protocol 'work mode' executed successfully" in res_wm

    # Test slash commands
    res_list = await cli._handle_slash_command("/protocol list")
    print(f"✓ /protocol list output: {res_list}")

    res_del = await cli._handle_slash_command("/protocol delete non_existent_protocol")
    print(f"✓ /protocol delete non-existent output: {res_del}")

asyncio.run(test_triggers())

print("\nAll Protocol System tests PASSED successfully!")
