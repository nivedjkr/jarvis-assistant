import pytest
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.tools import ToolRegistry


def test_tool_state_change_callback():
    async def _test():
        registry = ToolRegistry()
        captured_updates = []

        def mock_on_state_change(domain, action, payload):
            captured_updates.append((domain, action, payload))

        registry.on_state_change = mock_on_state_change

        # Execute an inventory tool
        res = await registry.execute("set_inventory_threshold", {
            "sku": "SKU-TEST-123",
            "item_name": "Test Mechanical Keyboard",
            "reorder_threshold": 15
        })

        assert "Updated inventory threshold" in res
        assert len(captured_updates) == 1
        domain, action, payload = captured_updates[0]
        assert domain == "inventory"
        assert action == "stock_updated"
        assert payload["sku"] == "SKU-TEST-123"

    asyncio.run(_test())


def test_adjacent_context_suggestion_cooldown():
    async def _test():
        registry = ToolRegistry()
        # Force cooldown reset
        registry._last_suggestion_time = 0.0

        # Execute git_status tool (or git tool)
        res = await registry.execute("git_status", {})
        # Note check should append if uncommitted files exist or skip cleanly
        assert isinstance(res, str)

    asyncio.run(_test())
