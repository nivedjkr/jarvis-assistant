import pytest
from fastapi.testclient import TestClient
from jarvis.tools import ToolRegistry
from jarvis.api import app

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def tool_registry():
    return ToolRegistry()

@pytest.mark.asyncio
async def test_git_diff_tool_execution(tool_registry):
    """Test git_diff tool returns valid diff output or stat."""
    diff_res = await tool_registry.execute("git_diff", {})
    assert isinstance(diff_res, str)

    stat_res = await tool_registry.execute("git_diff", {"stat_only": True})
    assert isinstance(stat_res, str)

def test_workspace_diff_endpoint_clean_and_stat(client):
    """Test /workspace/diff endpoint returns structured json with diff, stat, and clean fields."""
    response = client.get("/workspace/diff")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "diff" in data
    assert "stat" in data
    assert "clean" in data
    assert "path" in data

def test_workspace_diff_endpoint_sandbox_rejection(client):
    """Test /workspace/diff rejects paths violating sandbox security policies."""
    blocked_path = "C:\\Windows\\System32"
    response = client.get(f"/workspace/diff?path={blocked_path}")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert "ACCESS DENIED" in data["error"] or "outside allowed" in data["error"]
