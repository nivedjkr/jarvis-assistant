import os
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from jarvis.tools import ToolRegistry


def test_dangerously_skip_permissions_default_false():
    """Verify that dangerously_skip_permissions is disabled by default."""
    # Ensure env var is clean
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("JARVIS_DANGEROUSLY_SKIP_PERMISSIONS", None)
        registry = ToolRegistry()
        assert registry.dangerously_skip_permissions is False


def test_dangerously_skip_permissions_env_var():
    """Verify initialization from JARVIS_DANGEROUSLY_SKIP_PERMISSIONS environment variable."""
    with patch.dict(os.environ, {"JARVIS_DANGEROUSLY_SKIP_PERMISSIONS": "true"}):
        registry = ToolRegistry()
        assert registry.dangerously_skip_permissions is True

    with patch.dict(os.environ, {"JARVIS_DANGEROUSLY_SKIP_PERMISSIONS": "1"}):
        registry = ToolRegistry()
        assert registry.dangerously_skip_permissions is True

    with patch.dict(os.environ, {"JARVIS_DANGEROUSLY_SKIP_PERMISSIONS": "0"}):
        registry = ToolRegistry()
        assert registry.dangerously_skip_permissions is False


def test_dangerously_skip_permissions_toggle():
    """Verify set_dangerously_skip_permissions dynamically toggles mode."""
    registry = ToolRegistry()
    assert registry.dangerously_skip_permissions is False

    registry.set_dangerously_skip_permissions(True)
    assert registry.dangerously_skip_permissions is True

    registry.set_dangerously_skip_permissions(False)
    assert registry.dangerously_skip_permissions is False


@pytest.mark.asyncio
async def test_dangerously_skip_permissions_bypasses_risky_gate():
    """Verify risky tools execute directly when dangerously_skip_permissions is active."""
    registry = ToolRegistry(dangerously_skip_permissions=False)

    # 1. Without flag: run_command triggers confirmation gate
    res_gated = await registry.execute("run_command", {"command": "cmd /c echo test_gated"})
    assert "PENDING_CONFIRMATION" in res_gated
    assert len(registry.pending_actions) > 0

    # 2. With flag: run_command executes directly without pending confirmation
    registry.set_dangerously_skip_permissions(True)
    res_bypassed = await registry.execute("run_command", {"command": "cmd /c echo hello_skip"})
    assert "PENDING_CONFIRMATION" not in res_bypassed
    assert "CONFIRMATION REQUIRED" not in res_bypassed
    assert "hello_skip" in res_bypassed


def test_hard_security_rule_no_confirmed_in_schemas():
    """Hard rule verification: No tool's OpenAI JSON schema may expose confirmed/is_confirmed."""
    registry = ToolRegistry(dangerously_skip_permissions=True)
    for schema in registry.schemas:
        fn_info = schema.get("function", {})
        props = fn_info.get("parameters", {}).get("properties", {})
        assert "confirmed" not in props, f"Tool '{fn_info.get('name')}' exposes 'confirmed' in schema!"
        assert "is_confirmed" not in props, f"Tool '{fn_info.get('name')}' exposes 'is_confirmed' in schema!"
        assert "dangerously_skip_permissions" not in props, f"Tool '{fn_info.get('name')}' exposes bypass in schema!"


@pytest.mark.asyncio
async def test_cli_slash_command_dangerously_skip_permissions():
    """Verify CLI /dangerously-skip-permissions slash command enables and disables the mode."""
    from jarvis.cli import JarvisAssistant

    with patch("jarvis.cli.BOOT_ART", ""):
        assistant = JarvisAssistant(dangerously_skip_permissions=False)
        assert assistant.tools.dangerously_skip_permissions is False

        # Toggle ON
        res_on = await assistant.process("/dangerously-skip-permissions on")
        assert "DANGEROUSLY SKIP PERMISSIONS ENABLED" in res_on
        assert assistant.tools.dangerously_skip_permissions is True

        # Toggle OFF
        res_off = await assistant.process("/dangerously-skip-permissions off")
        assert "Safety confirmation gates restored" in res_off
        assert assistant.tools.dangerously_skip_permissions is False

        # Toggle without arguments
        res_toggle = await assistant.process("/skip-permissions")
        assert "DANGEROUSLY SKIP PERMISSIONS ENABLED" in res_toggle
        assert assistant.tools.dangerously_skip_permissions is True
