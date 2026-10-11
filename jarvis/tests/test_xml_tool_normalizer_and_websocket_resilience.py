import pytest
import asyncio
from jarvis.tool_normalizer import (
    normalize_tool_calls,
    classify_response,
    is_unresolved_tool_call,
    ResponseClassification
)
from jarvis.proactive_engine import RelevanceGate


def test_xml_tool_call_normalization_nemotron_format():
    """Verify normalization of Nemotron-style XML tool calls with function and parameter tags."""
    raw = """<tool_call>
<function=inspect_project>
<parameter=path>
D:\\phantomX
</parameter>
</function>
</tool_call>"""
    tools = {"inspect_project", "run_tests", "search_files"}
    normalized = normalize_tool_calls(raw, registered_tools=tools)
    classification = classify_response(raw, registered_tools=tools)

    assert normalized is not None
    assert len(normalized) == 1
    assert normalized[0]["name"] == "inspect_project"
    assert normalized[0]["arguments"] == {"path": "D:\\phantomX"}
    assert classification == ResponseClassification.TOOL_CALL


def test_xml_tool_call_normalization_multiple_parameters():
    """Verify normalization of multi-parameter XML tool calls."""
    raw = """<tool_call>
<function=search_files>
<parameter=pattern>
phantomX
</parameter>
<parameter=path>
D:\\
</parameter>
</function>
</tool_call>"""
    tools = {"inspect_project", "run_tests", "search_files"}
    normalized = normalize_tool_calls(raw, registered_tools=tools)

    assert normalized is not None
    assert len(normalized) == 1
    assert normalized[0]["name"] == "search_files"
    assert normalized[0]["arguments"] == {"pattern": "phantomX", "path": "D:\\"}


def test_xml_tool_call_json_inside_tag():
    """Verify normalization when tool call block encapsulates JSON."""
    raw = """<tool_call>
{"name": "run_tests", "arguments": {"path": "D:\\\\phantomx"}}
</tool_call>"""
    tools = {"inspect_project", "run_tests", "search_files"}
    normalized = normalize_tool_calls(raw, registered_tools=tools)

    assert normalized is not None
    assert len(normalized) == 1
    assert normalized[0]["name"] == "run_tests"
    assert normalized[0]["arguments"] == {"path": "D:\\phantomx"}


def test_unresolved_tool_call_firewall_blocks_xml():
    """Verify that the final response firewall catches unresolved XML tool calls."""
    raw = """<tool_call>
<function=inspect_project>
<parameter=path>
D:\\phantomX
</parameter>
</function>
</tool_call>"""
    tools = {"inspect_project", "run_tests"}
    assert is_unresolved_tool_call(raw, registered_tools=tools) is True

    plain_text = "Here is the project overview for PhantomX, sir."
    assert is_unresolved_tool_call(plain_text, registered_tools=tools) is False


@pytest.mark.asyncio
async def test_relevance_gate_excludes_direct_check_commands():
    """Verify that RelevanceGate excludes direct operational commands from generic proactive web searches."""
    gate = RelevanceGate()

    # Direct project checking should NOT trigger background web searches for 'project topic'
    res1 = await gate.evaluate("check my phantomX project", "Inspecting project now.")
    assert res1["should_investigate"] is False

    res2 = await gate.evaluate("inspect phantomx and run tests", "Running tests now.")
    assert res2["should_investigate"] is False

    res3 = await gate.evaluate("run tests on D:\\phantomx", "Starting test runner.")
    assert res3["should_investigate"] is False


def test_websocket_decoupled_ping_pong():
    """Verify that websocket connection endpoint immediately handles ping without socket starvation."""
    from fastapi.testclient import TestClient
    from jarvis.api import app, WS_AUTH_TOKEN

    client = TestClient(app)
    with client.websocket_connect(f"/ws?token={WS_AUTH_TOKEN}") as ws:
        status_msg = ws.receive_json()
        assert status_msg["type"] == "status"
        assert status_msg["status"] == "connected"

        # Send ping and receive immediate pong
        ws.send_json({"type": "ping"})
        pong_msg = ws.receive_json()
        assert pong_msg == {"type": "pong"}


def test_mobile_diff_view_websocket_event():
    """Verify that mobile /diff slash command emits structured diff_view payload over WebSocket."""
    from fastapi.testclient import TestClient
    from jarvis.api import app, WS_AUTH_TOKEN

    client = TestClient(app)
    with client.websocket_connect(f"/ws?token={WS_AUTH_TOKEN}") as ws:
        status_msg = ws.receive_json()
        assert status_msg["type"] == "status"
        assert status_msg["status"] == "connected"

        # Trigger slash command /diff
        ws.send_json({"type": "slash_command", "command": "/diff"})
        
        # Read messages until diff_view arrives
        found_diff = False
        for _ in range(5):
            msg = ws.receive_json()
            if msg.get("type") == "diff_view":
                assert "diff" in msg
                assert "stat" in msg
                assert "path" in msg
                found_diff = True
                break
        assert found_diff is True


def test_mobile_confirm_action_websocket():
    """Verify that mobile inline confirmation card dispatches confirm_action message correctly."""
    from fastapi.testclient import TestClient
    from jarvis.api import app, WS_AUTH_TOKEN, tool_registry

    # Register mock pending action
    def sample_dangerous_action():
        return "Executed dangerous action safely."

    act_msg = tool_registry.create_pending_action(
        name="dangerous_tool",
        args={"target": "test"},
        fn=sample_dangerous_action,
        preview="Test preview description"
    )
    # Parse act_id
    act_id = act_msg.split("Action ID: ")[1].split("\n")[0].strip()
    assert act_id in tool_registry.pending_actions

    client = TestClient(app)
    with client.websocket_connect(f"/ws?token={WS_AUTH_TOKEN}") as ws:
        status_msg = ws.receive_json()
        assert status_msg["type"] == "status"

        # Send confirm_action from mobile UI
        ws.send_json({"type": "confirm_action", "action_id": act_id})
        resp = ws.receive_json()
        assert resp["type"] == "response"
        assert "Executed dangerous action safely." in resp["text"]


def test_xml_tool_call_git_add_granular():
    """Verify normalization of git_add XML tool calls emitted by Nemotron."""
    from jarvis.tool_normalizer import normalize_tool_calls, classify_response, ResponseClassification

    raw = """<tool_call>
<function=git_add>
<parameter=path>
.
</parameter>
</function>
</tool_call>"""
    tools = {"git_add", "git_commit", "git_push", "git_status"}
    normalized = normalize_tool_calls(raw, registered_tools=tools)
    classification = classify_response(raw, registered_tools=tools)

    assert normalized is not None
    assert len(normalized) == 1
    assert normalized[0]["name"] == "git_add"
    assert normalized[0]["arguments"] == {"path": "."}
    assert classification == ResponseClassification.TOOL_CALL


def test_xml_tool_call_alias_resolution():
    """Verify that git_stage alias resolves to git_add."""
    from jarvis.tool_normalizer import normalize_tool_calls

    raw = """<tool_call>
<function=git_stage>
<parameter=path>
README.md
</parameter>
</function>
</tool_call>"""
    tools = {"git_add", "git_status"}
    normalized = normalize_tool_calls(raw, registered_tools=tools)

    assert normalized is not None
    assert len(normalized) == 1
    assert normalized[0]["name"] == "git_add"
    assert normalized[0]["arguments"] == {"path": "README.md"}


def test_unregistered_xml_tool_call_blocked_by_firewall():
    """Verify that even unregistered tool call XML is caught by the firewall."""
    from jarvis.tool_normalizer import is_unresolved_tool_call

    raw = """<tool_call>
<function=non_existent_tool_123>
<parameter=foo>
bar
</parameter>
</function>
</tool_call>"""
    registered = {"git_status", "search_obsidian"}
    # Must detect as unresolved even though non_existent_tool_123 is not in registered!
    assert is_unresolved_tool_call(raw, registered_tools=registered) is True


def test_strip_raw_tool_tags():
    """Verify that strip_raw_tool_tags completely eliminates leaked XML tags."""
    from jarvis.tool_normalizer import strip_raw_tool_tags

    raw_leaked = """<tool_call>
<function=git_add>
<parameter=path>
.
</parameter>
</function>
</tool_call>"""
    cleaned = strip_raw_tool_tags(raw_leaked)
    assert cleaned == ""

    mixed_text = """I will stage the changes now.
<tool_call>
<function=git_add>
<parameter=path>.</parameter>
</function>
</tool_call>"""
    cleaned_mixed = strip_raw_tool_tags(mixed_text)
    assert cleaned_mixed == "I will stage the changes now."


@pytest.mark.asyncio
async def test_git_push_requires_confirmation_in_tool_registry():
    """Verify that git_push is gated as a RISKY_TOOL requiring human confirmation."""
    from jarvis.api import tool_registry

    # Reset any dangerous skip permissions flag
    orig_skip = tool_registry.dangerously_skip_permissions
    tool_registry.dangerously_skip_permissions = False
    try:
        res = await tool_registry.execute("git_push", {"remote": "origin", "branch": "main"})
        assert "PENDING_CONFIRMATION" in res or "Action ID:" in res
    finally:
        tool_registry.dangerously_skip_permissions = orig_skip
