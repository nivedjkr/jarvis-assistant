"""
Unit tests for JARVIS /paste and /multiline slash commands.
"""

import sys
import os
import unittest
import asyncio
from unittest.mock import patch, MagicMock

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from jarvis.cli import JARVISCLI, get_clipboard_text


class TestPasteCommands(unittest.TestCase):

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

    def test_get_clipboard_text_returns_string(self):
        """Verify get_clipboard_text returns a string without raising exceptions."""
        result = get_clipboard_text()
        self.assertIsInstance(result, str)

    @patch("jarvis.cli.get_clipboard_text", return_value="Line 1: Hello JARVIS\nLine 2: Multi-line sentence test\nLine 3: End of prompt")
    def test_handle_paste_command_with_clipboard(self, mock_clip):
        """Verify /paste reads clipboard text and processes single command."""
        async def run_test():
            with patch.object(self.cli, "process_single_command", return_value="Processed clipboard text successfully.") as mock_proc:
                res = await self.cli._handle_slash_command("/paste summarize this")
                mock_proc.assert_called_once_with("summarize this:\n\nLine 1: Hello JARVIS\nLine 2: Multi-line sentence test\nLine 3: End of prompt")
                self.assertEqual(res, "Processed clipboard text successfully.")

        asyncio.run(run_test())

    @patch("jarvis.cli.get_clipboard_text", return_value="")
    def test_handle_paste_command_empty_clipboard(self, mock_clip):
        """Verify /paste handles empty clipboard gracefully."""
        async def run_test():
            res = await self.cli._handle_slash_command("/paste")
            self.assertIn("No text found on clipboard", res)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
