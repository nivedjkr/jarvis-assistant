"""
Automated & Visual Verification Suite for Futuristic JARVIS Terminal UI
Verifies ASCII Banner, Boot Checklist, Response Panels, User Message Panels, Tool Tags, Status Bar, and Animations.
"""

import sys
import os
import unittest
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path

root_dir = str(Path(__file__).resolve().parents[3])
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from jarvis.ui import ui, UIState, BANNER_ASCII, PRIMARY, ERROR, SUCCESS, WARNING


class TestFuturisticUI(unittest.TestCase):

    def test_1_ascii_banner_text(self):
        """Verify ASCII banner spells JARVIS cleanly with exact character matching."""
        self.assertIn("██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗", BANNER_ASCII)
        self.assertIn("╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║", BANNER_ASCII)
        # Ensure it does NOT contain 'ZARVIS' ASCII art lines
        self.assertNotIn("███████╗.█████╗", BANNER_ASCII)

    def test_2_banner_rendering(self):
        """Test banner rendering execution."""
        print("\n--- Test 2: Rendering Startup Boot Banner ---")
        ui.render_banner()
        self.assertTrue(ui._banner_shown)

    def test_3_boot_checklist_rendering(self):
        """Test boot sequence subsystem checklist rendering."""
        print("\n--- Test 3: Rendering Boot Checklist ---")
        dummy_checks = [
            ("Database", "connected", "SQLite DB online (47 facts)", True),
            ("NVIDIA NIM API", "reachable", "latency: 312ms", True),
            ("Voice / TTS", "ready", "en-GB-RyanNeural", True),
            ("Monitor threads", "running", "reminders, security, prices", True),
            ("Microphone", "not found", "voice input disabled", False)
        ]
        ui.render_boot_checklist(dummy_checks)

    def test_4_panels_and_dividers(self):
        """Test response panel, user message panel, section dividers, and errors."""
        print("\n--- Test 4: Rendering User & Assistant Panels ---")
        ui.render_user_message("open notepad and calculate total")
        ui.render_divider()
        ui.render_response("Notepad opened, sir. Ready for instructions.")
        ui.render_error("Failed to open application: chrome", "process exited immediately")

    def test_5_tool_call_formatting(self):
        """Test fixed-width bracketed tool tags."""
        print("\n--- Test 5: Rendering Tool Tags ---")
        ui.render_tool_call("EXEC", "opening notepad.exe")
        ui.render_tool_call("TOOL", "read_file → test.txt")
        ui.render_tool_call("MEM", "saved fact: prefers Python")
        ui.render_tool_call("PROTO", "activating: work_mode")
        ui.render_tool_call("ALERT", "CPU usage: 87%")
        ui.render_tool_call("WARN", "confirmation required")
        ui.render_tool_call("ERROR", "failed to open chrome")

    def test_6_status_bar_and_tables(self):
        """Test status bar string formatting and command reference tables."""
        print("\n--- Test 6: Rendering Status Bar & Tables ---")
        ui.set_state(UIState.IDLE)
        bar = ui.render_status_bar(memory_count=47)
        self.assertIn("◈ JARVIS", bar)
        self.assertIn("MEM: 47 facts", bar)
        self.assertIn("SECURE", bar)
        ui.print_status_bar(memory_count=47)

        headers = ["COMMAND", "DESCRIPTION"]
        rows = [
            ["/help", "Show command reference"],
            ["/remember", "Save a fact"],
            ["/diagnose", "Check system health"]
        ]
        ui.render_table("JARVIS COMMAND REFERENCE", headers, rows)


if __name__ == "__main__":
    unittest.main()
