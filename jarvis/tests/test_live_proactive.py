import pytest
import os
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from jarvis.api_client import JarvisAPIClient

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.mark.anyio
async def test_proactive_chat():
    client = JarvisAPIClient()
    
    print("\n--- Test 1: Genuinely Ambiguous Request ---")
    req_ambiguous = "clean up the repo"
    print(f"User: '{req_ambiguous}'")
    client.add_user_message(req_ambiguous, session_id="test_ambig")
    resp_ambig = await client.chat(session_id="test_ambig")
    print(f"JARVIS: {resp_ambig}\n")
    assert "?" in resp_ambig  # Should ask a clarifying question
    
    print("--- Test 2: Unambiguous Request ---")
    req_unambiguous = "What time is it right now?"
    print(f"User: '{req_unambiguous}'")
    client.add_user_message(req_unambiguous, session_id="test_unambig")
    resp_unambig = await client.chat(session_id="test_unambig")
    print(f"JARVIS: {resp_unambig}\n")
    assert len(resp_unambig) > 0

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_proactive_chat())
