import os
import pytest
from fastapi.testclient import TestClient
from jarvis.api import app, api_client
from jarvis.semantic_memory import SemanticMemory

def test_semantic_memory_prewarm():
    mem = SemanticMemory()
    mem.prewarm()
    assert mem.model is not None

def test_mobile_static_files():
    client = TestClient(app)
    
    res_index = client.get("/mobile/")
    assert res_index.status_code == 200
    assert "J.A.R.V.I.S." in res_index.text
    
    res_app = client.get("/mobile/app.js")
    assert res_app.status_code == 200
    assert "initOrbVisualizer" in res_app.text
    
    res_css = client.get("/mobile/styles.css")
    assert res_css.status_code == 200
    assert "orbCanvas" in res_css.text
    
    res_cfg = client.get("/mobile/config.json")
    assert res_cfg.status_code == 200
    assert "ws_token" in res_cfg.json()

def test_vitals_endpoint():
    client = TestClient(app)
    res = client.get("/vitals")
    assert res.status_code == 200
    data = res.json()
    assert "cpu_usage" in data
    assert "ram_usage" in data


@pytest.mark.asyncio
async def test_concurrent_semantic_memory_search():
    import asyncio
    from jarvis.api_client import JarvisAPIClient
    client = JarvisAPIClient()
    client.semantic_memory = SemanticMemory()
    client.semantic_memory.add_fact("Jarvis loves latency optimizations", category="system")

    # Run 5 concurrent memory lookups offloaded via asyncio.to_thread
    tasks = [
        asyncio.to_thread(client.get_messages_with_memory, f"Query iteration {i}", None)
        for i in range(5)
    ]
    results = await asyncio.gather(*tasks)
    assert len(results) == 5
    for msgs in results:
        assert isinstance(msgs, list)
        assert len(msgs) >= 1


@pytest.mark.asyncio
async def test_chat_with_tools_latency_logging(capsys):
    from jarvis.api_client import JarvisAPIClient
    client = JarvisAPIClient()
    client.semantic_memory = SemanticMemory()
    client.new_session("test_latency_sess")
    client.add_user_message("What is the status of the server?", session_id="test_latency_sess")

    class MockProvider:
        name = "MockProvider"
        async def chat(self, messages, tools=None, max_tokens=2048):
            return "Server status is nominal, sir."

    client.provider = MockProvider()

    async def mock_executor(name, args):
        return "OK"

    response = await client.chat_with_tools(
        tool_schemas=[],
        tool_executor=mock_executor,
        session_id="test_latency_sess"
    )
    captured = capsys.readouterr()
    assert "[LATENCY]" in captured.out
    assert "memory=" in captured.out
    assert "llm=" in captured.out
    assert "tools=" in captured.out
    assert "total=" in captured.out


