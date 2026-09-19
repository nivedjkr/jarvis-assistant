import pytest
import time
from jarvis.workspace_sentinel import WorkspaceSentinel, PerceptualEvent, get_workspace_sentinel
from jarvis.tools import ToolRegistry, validate_tool_schemas
from jarvis.cli import JarvisAssistant


def test_perceptual_event_serialization():
    """Verify PerceptualEvent data structure and to_dict method."""
    evt = PerceptualEvent(
        id="evt_test_01",
        event_type="WINDOW_FOCUS",
        summary="User switched to VS Code",
        details={"app": "Code.exe"}
    )
    d = evt.to_dict()
    assert d["id"] == "evt_test_01"
    assert d["event_type"] == "WINDOW_FOCUS"
    assert d["summary"] == "User switched to VS Code"
    assert d["details"]["app"] == "Code.exe"


def test_workspace_sentinel_scan_and_callback():
    """Verify manual scan and event callback dispatch."""
    sentinel = WorkspaceSentinel()
    received = []

    def on_event(e: PerceptualEvent):
        received.append(e)

    sentinel.add_callback(on_event)
    events = sentinel.scan_once()
    
    # We registered callback, verify status
    st = sentinel.get_status()
    assert "running" in st
    assert "buffered_events_count" in st
    assert "last_active_window" in st
    
    sentinel.remove_callback(on_event)
    assert on_event not in sentinel.callbacks


def test_sentinel_background_lifecycle():
    """Test starting and cleanly stopping the background sentinel thread."""
    sentinel = WorkspaceSentinel()
    assert sentinel.running is False
    
    # Start
    started = sentinel.start(interval_seconds=1.0)
    assert started is True
    assert sentinel.running is True
    
    time.sleep(0.1)
    
    # Stop
    stopped = sentinel.stop()
    assert stopped is True
    assert sentinel.running is False


@pytest.mark.asyncio
async def test_sentinel_tools_and_schemas():
    """Verify sentinel tools are registered in ToolRegistry and schemas validate."""
    registry = ToolRegistry()
    assert validate_tool_schemas(registry) is True
    assert "get_sentinel_events" in registry.tools
    assert "scan_workspace_now" in registry.tools

    # Test tool execution
    scan_res = await registry.execute("scan_workspace_now", {})
    assert "Workspace scan" in scan_res

    events_res = await registry.execute("get_sentinel_events", {"limit": 5})
    assert isinstance(events_res, str)


@pytest.mark.asyncio
async def test_cli_sentinel_slash_command():
    """Test /sentinel slash command in CLI."""
    app = JarvisAssistant()
    
    # Status
    res_status = await app.process("/sentinel")
    assert "Streaming Perception Sentinel" in res_status
    
    # Scan
    res_scan = await app.process("/sentinel scan")
    assert "Sentinel scan complete" in res_scan or "Workspace scan" in res_scan
