import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis.diagnostics import (
    HealthCheckReport,
    HealthCheckItem,
    run_diagnostics_sync,
    check_port_8765,
    check_sqlite_db,
    check_github_auth,
    check_obsidian,
    check_voice_tts
)


def test_health_check_item_structure():
    item = HealthCheckItem("Test Check", "TestCategory", critical=True)
    assert item.name == "Test Check"
    assert item.category == "TestCategory"
    assert item.critical is True
    assert item.status == "PENDING"
    
    d = item.to_dict()
    assert d["name"] == "Test Check"
    assert d["status"] == "PENDING"


def test_health_check_report_aggregation():
    report = HealthCheckReport()
    
    item1 = HealthCheckItem("Check 1", "Core", critical=True)
    item1.status = "PASS"
    item1.message = "OK"
    report.add(item1)
    assert report.overall_status == "OK"

    item2 = HealthCheckItem("Check 2", "Integrations", critical=False)
    item2.status = "WARN"
    item2.message = "Optional warning"
    report.add(item2)
    assert report.overall_status == "WARN"

    item3 = HealthCheckItem("Check 3", "API", critical=True)
    item3.status = "FAIL"
    item3.message = "Critical failure"
    report.add(item3)
    assert report.overall_status == "ERROR"

    plain = report.format_plain()
    assert "JARVIS STARTUP DIAGNOSTICS" in plain
    assert "STATUS: [FAIL] SYSTEM CRITICAL FAILURE DETECTED" in plain


def test_individual_checks():
    report = HealthCheckReport()
    
    # Port check
    port_item = check_port_8765(report)
    assert port_item.status in ["PASS", "WARN", "FAIL"]
    
    # SQLite check
    sqlite_item = check_sqlite_db(report)
    assert sqlite_item.status == "PASS"

    # Voice check
    voice_item = check_voice_tts(report)
    assert voice_item.status in ["PASS", "WARN"]

    # Obsidian check
    obsidian_item = check_obsidian(report)
    assert obsidian_item.status in ["PASS", "WARN"]


def test_run_diagnostics_sync():
    report = run_diagnostics_sync(check_nvidia=False)
    assert isinstance(report, HealthCheckReport)
    assert len(report.items) > 0
    assert report.overall_status in ["OK", "WARN", "ERROR"]
    dict_rep = report.to_dict()
    assert "overall_status" in dict_rep
    assert "items" in dict_rep
