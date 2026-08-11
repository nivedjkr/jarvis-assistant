"""
Automated Verification Suite for JARVIS DuckDuckGo Web Search Integration
Tests DuckDuckGoSearchTool, ToolRegistry integration, and CLI slash command / natural language handling.
"""

import sys
import os
import unittest
import asyncio

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path

root_dir = str(Path(__file__).resolve().parents[3])
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from jarvis.tools import ToolRegistry, DuckDuckGoSearchTool
from jarvis.cli import JARVISCLI


class TestDuckDuckGoSearch(unittest.TestCase):

    def setUp(self):
        self.registry = ToolRegistry()
        self.cli = JARVISCLI()

    def test_1_tool_registration(self):
        """Verify DuckDuckGoSearchTool is registered in default tools."""
        tool = self.registry.get_tool("duckduckgo_search")
        self.assertIsNotNone(tool)
        self.assertIsInstance(tool, DuckDuckGoSearchTool)

    def test_2_tool_execution(self):
        """Verify DuckDuckGoSearchTool returns formatted results."""
        tool = DuckDuckGoSearchTool()
        result = asyncio.run(tool.execute(query="Python programming", max_results=2))
        self.assertIn("DuckDuckGo", result)
        self.assertTrue("Python" in result or "No DuckDuckGo" in result)

    def test_3_cli_slash_command(self):
        """Verify /search slash command handles queries correctly."""
        res = asyncio.run(self.cli._handle_slash_command("/search Python language"))
        self.assertIn("DuckDuckGo", res)
        self.assertTrue("Python" in res or "No DuckDuckGo" in res)

    def test_4_cli_slash_command_usage(self):
        """Verify /search without query returns usage message."""
        res = asyncio.run(self.cli._handle_slash_command("/search"))
        self.assertIn("Usage: /search <query>", res)

    def test_5_cli_natural_language_search(self):
        """Verify natural language DuckDuckGo search queries."""
        res = asyncio.run(self.cli.process_single_command("search duckduckgo for latest news"))
        self.assertIsNotNone(res)
        self.assertIn("DuckDuckGo", res)


if __name__ == "__main__":
    unittest.main()
