"""
Test Output-Only Text-to-Speech Response Reading for JARVIS
"""
import sys
import asyncio
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import os
from pathlib import Path

root_dir = str(Path(__file__).resolve().parent.parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

print("Testing JARVIS Response Text-to-Speech...\n")

from jarvis.cli import JARVISCLI
from jarvis.voice import _clean_text_for_speech

cli = JARVISCLI()
vm = cli.voice_manager

# Test 1: Text Cleaning & Code Block Omission
print("--- Test 1: Text Cleaning & Code Block Omission ---")
sample_markdown = """
Here is the code you requested, **sir**:
```python
def hello():
    print("Hello world")
```
Check out `https://github.com` for details.
"""

cleaned_no_code = _clean_text_for_speech(sample_markdown, speak_code_blocks=False)
print(f"✓ Cleaned (speak_code_blocks=False):\n   '{cleaned_no_code}'")
assert "code block omitted" in cleaned_no_code
assert "https://" not in cleaned_no_code

cleaned_with_code = _clean_text_for_speech(sample_markdown, speak_code_blocks=True)
print(f"✓ Cleaned (speak_code_blocks=True):\n   '{cleaned_with_code}'")
assert "print" in cleaned_with_code

# Test 2: Slash Commands (/speak & /mute)
print("\n--- Test 2: Slash Commands (/speak on|off & /mute) ---")
async def test_slash():
    res1 = await cli._handle_slash_command("/speak off")
    print(f"✓ /speak off: {res1}")
    assert vm.speak_responses is False

    res2 = await cli._handle_slash_command("/speak on")
    print(f"✓ /speak on: {res2}")
    assert vm.speak_responses is True

    res3 = await cli._handle_slash_command("/mute")
    print(f"✓ /mute: {res3}")
    assert vm.tts.is_cancelled is True

asyncio.run(test_slash())

print("\nAll Response Text-to-Speech tests PASSED successfully!")
