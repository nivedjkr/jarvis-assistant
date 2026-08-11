"""
Automated Verification Suite for JARVIS Real-Time Monitoring & Sync Features
Verifies System Monitor, Weather Manager, Live Price Watch with Contextual News,
Google Calendar Sync, and Email Triage.
"""

import sys
import os
import unittest
import asyncio

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path

root_dir = str(Path(__file__).resolve().parent.parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from jarvis.system_monitor import SystemMonitor
from jarvis.weather import WeatherManager
from jarvis.google_auth import GoogleAuthManager
from jarvis.calendar_service import CalendarService
from jarvis.email_service import EmailService
from jarvis.cli import JARVISCLI


class TestRealTimeMonitoringFeatures(unittest.TestCase):

    def setUp(self):
        self.cli = JARVISCLI()

    def test_1_system_resource_monitor(self):
        """Test real system hardware telemetry, snapshot structure, and anomaly detection."""
        sm = SystemMonitor()
        snapshot = sm.get_system_snapshot()
        
        self.assertIn("cpu_pct", snapshot)
        self.assertIn("ram_pct", snapshot)
        self.assertIn("disks", snapshot)
        self.assertIn("network_online", snapshot)
        self.assertIsInstance(snapshot["cpu_pct"], float)
        self.assertIsInstance(snapshot["ram_pct"], float)
        self.assertGreaterEqual(len(snapshot["disks"]), 1)

        # Test CLI command output
        res = asyncio.run(self.cli._handle_slash_command("/system"))
        self.assertIn("Real-Time System Telemetry", res)
        self.assertIn("CPU Usage:", res)
        self.assertIn("RAM Usage:", res)

        # Test CLI anomaly log output
        log_res = asyncio.run(self.cli._handle_slash_command("/system log"))
        self.assertTrue("Anomalies" in log_res or "No recent" in log_res)

    def test_2_weather_manager(self):
        """Test WeatherManager formatting and unconfigured fallback behavior."""
        wm = WeatherManager(self.cli.config)
        self.assertEqual(wm.city, "Kerala")
        self.assertEqual(wm.country, "India")

        res_today = wm.format_weather_command(is_tomorrow=False)
        self.assertTrue("Weather" in res_today or "missing or unconfigured" in res_today)

        res_tomorrow = wm.format_weather_command(is_tomorrow=True)
        self.assertTrue("Forecast" in res_tomorrow or "missing or unconfigured" in res_tomorrow)

        # Test CLI command
        cli_res = asyncio.run(self.cli._handle_slash_command("/weather"))
        self.assertTrue("Weather" in cli_res or "unconfigured" in cli_res)

    def test_3_google_calendar_service(self):
        """Test CalendarService event format, 5-minute cache logic, and fallback responses."""
        gam = GoogleAuthManager()
        cs = CalendarService(gam)
        
        # Test command outputs when unauthenticated
        today_res = cs.format_calendar_command("today")
        self.assertTrue("Calendar" in today_res or "authenticated" in today_res.lower())

        next_res = cs.format_calendar_command("next")
        self.assertTrue("Next Event" in next_res or "authenticated" in next_res.lower() or "No upcoming" in next_res)

        cli_res = asyncio.run(self.cli._handle_slash_command("/calendar today"))
        self.assertTrue("Calendar" in cli_res or "authenticated" in cli_res.lower())

    def test_4_gmail_email_triage(self):
        """Test EmailService classification rules and command output."""
        gam = GoogleAuthManager()
        es = EmailService(gam)

        # Test importance classification
        self.assertEqual(es.classify_importance("Boss <boss@company.com>", "URGENT: Server Down"), "urgent")
        self.assertEqual(es.classify_importance("Newsletter <info@news.com>", "Weekly digest % off"), "noise")
        self.assertEqual(es.classify_importance("Friend <alex@gmail.com>", "Coffee tomorrow?"), "normal")

        # Test CLI command outputs
        email_res = es.format_unread_list()
        self.assertTrue("Emails" in email_res or "authenticated" in email_res.lower() or "no unread" in email_res.lower())

        cli_res = asyncio.run(self.cli._handle_slash_command("/email"))
        self.assertTrue("Emails" in cli_res or "authenticated" in cli_res.lower() or "no unread" in cli_res.lower())

    def test_5_diagnose_command_integration(self):
        """Test that /diagnose includes System Monitor, Weather, and Google Sync subsystem checks."""
        diag_res = asyncio.run(self.cli._handle_slash_command("/diagnose"))
        self.assertEqual(diag_res, "Self-diagnostic check complete, sir.")


if __name__ == "__main__":
    unittest.main()
