"""
Automated Verification Suite for JARVIS Rebuilt Application Control System
Tests AppLaunchTool, AppCloseTool, psutil verification, safety guards, and open/close protocols.
"""

import sys
import os
import unittest
import asyncio
import psutil

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from jarvis.tools import ToolRegistry, AppLaunchTool, AppCloseTool
from jarvis.cli import JARVISCLI


class TestAppControlSystem(unittest.TestCase):

    def setUp(self):
        self.registry = ToolRegistry()
        self.cli = JARVISCLI()

    def test_1_open_app_notepad(self):
        """Test opening notepad with tiered strategy and psutil launch verification."""
        res = asyncio.run(self.cli.process_single_command("open notepad"))
        self.assertIn("Opened", res)
        self.assertIn("notepad", res.lower())
        
        # Verify process is running via psutil
        is_running = any("notepad" in p.name().lower() for p in psutil.process_iter(['name']))
        self.assertTrue(is_running, "Notepad process should be detected by psutil")

    def test_2_close_app_notepad(self):
        """Test closing notepad with graceful termination and psutil close verification."""
        # Ensure notepad is running first
        asyncio.run(self.cli.process_single_command("open notepad"))
        
        res = asyncio.run(self.cli.process_single_command("close notepad"))
        self.assertIn("Closed notepad", res)

        # Verify process is gone via psutil
        is_running = any("notepad" in p.name().lower() for p in psutil.process_iter(['name']))
        self.assertFalse(is_running, "Notepad process should be terminated and gone from psutil")

    def test_3_safety_check_protected_process(self):
        """Test safety guard prompt when user attempts to close terminal/python without confirm."""
        res = asyncio.run(self.cli.process_single_command("close cmd"))
        self.assertIn("That might be the terminal JARVIS is running in", res)

    def test_4_close_app_not_running(self):
        """Test closing an app that is not running."""
        res = asyncio.run(self.cli.process_single_command("close nonexistent_app_99"))
        self.assertIn("wasn't running", res)

    def test_5_full_protocol_mixed_sequence(self):
        """Test full protocol sequence: open notepad -> verify open -> close notepad -> verify closed."""
        # Step 1: Open notepad
        open_res = asyncio.run(self.cli.process_single_command("open notepad"))
        self.assertIn("Opened", open_res)
        
        # Step 2: Verify open via psutil
        self.assertTrue(any("notepad" in p.name().lower() for p in psutil.process_iter(['name'])))
        
        # Step 3: Close notepad
        close_res = asyncio.run(self.cli.process_single_command("close notepad"))
        self.assertIn("Closed notepad", close_res)
        
        # Step 4: Verify closed via psutil
        self.assertFalse(any("notepad" in p.name().lower() for p in psutil.process_iter(['name'])))


if __name__ == "__main__":
    unittest.main()
