"""
Unit tests for JARVIS Website & URL Opening features.
"""

import sys
import os
import unittest
import asyncio
from unittest.mock import patch, MagicMock

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from jarvis.cli import JARVISCLI
from jarvis.tools import WebsiteOpenTool, open_url, find_chrome_path


class TestWebsiteOpening(unittest.TestCase):

    @patch("jarvis.cli.NIMClient")
    @patch("jarvis.cli.Memory")
    @patch("jarvis.cli.VoiceManager")
    @patch("jarvis.cli.ProactiveMonitor")
    def setUp(self, mock_pm, mock_vm, mock_mem, mock_nim):
        dummy_config = {
            "memory": {"file": "dummy.json", "log_file": "dummy.log"},
            "tools": {"confirm_dangerous": False, "log_commands": False}
        }
        with patch.object(JARVISCLI, "_load_config", return_value=dummy_config):
            self.cli = JARVISCLI()

    def test_find_chrome_path(self):
        """Verify find_chrome_path locates Google Chrome executable."""
        path = find_chrome_path()
        self.assertIsNotNone(path)
        self.assertTrue(os.path.exists(path))
        self.assertIn("chrome", path.lower())

    @patch("jarvis.tools.subprocess.Popen")
    def test_open_domain_name_chrome(self, mock_popen):
        """Verify opening domain names like stackoverflow.com directly launches Google Chrome."""
        tool = WebsiteOpenTool()
        res = asyncio.run(tool.execute("stackoverflow.com"))
        self.assertIn("Google Chrome", res)
        self.assertIn("https://stackoverflow.com", res)

    @patch("jarvis.tools.subprocess.Popen")
    def test_open_alias_chrome(self, mock_popen):
        """Verify alias lookup for chatgpt launches Google Chrome."""
        tool = WebsiteOpenTool()
        res = asyncio.run(tool.execute("chatgpt"))
        self.assertIn("Google Chrome", res)
        self.assertIn("https://chat.openai.com", res)

    @patch("jarvis.tools.subprocess.Popen")
    def test_cli_check_tool_commands_google_dot_com(self, mock_popen):
        """Verify _check_tool_commands 'open google.com' routes to Google Chrome."""
        async def run_test():
            res = await self.cli._check_tool_commands("open google.com")
            self.assertIn("Google Chrome", res)

        asyncio.run(run_test())

    @patch("jarvis.tools.subprocess.Popen")
    def test_cli_check_tool_commands_full_url(self, mock_popen):
        """Verify _check_tool_commands 'open https://github.com/nivedjkr' routes to Google Chrome."""
        async def run_test():
            res = await self.cli._check_tool_commands("open https://github.com/nivedjkr")
            self.assertIn("Google Chrome", res)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
