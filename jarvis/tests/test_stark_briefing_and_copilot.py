import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from jarvis.stark_protocols import (
    StarkBriefingEngine,
    HouseProtocolsEngine,
    get_briefing_engine,
    get_protocols_engine
)
from jarvis.workspace_sentinel import WorkspaceSentinel, PerceptualEvent
from jarvis.tools import ToolRegistry


def test_stark_briefing_generation(tmp_path):
    engine = StarkBriefingEngine(workspace_path=tmp_path)
    
    greeting = engine.get_time_greeting()
    assert "sir" in greeting.lower()

    telemetry = engine.get_telemetry_summary()
    assert "CPU" in telemetry or "Telemetry" in telemetry

    workspace_sum = engine.get_workspace_summary()
    assert isinstance(workspace_sum, str)

    briefing = engine.generate_briefing()
    assert "Atmosphere:" in briefing
    assert "Hardware Telemetry:" in briefing
    assert "Workshop Status:" in briefing
    assert "100%" in briefing


def test_house_protocols_execution(tmp_path):
    engine = HouseProtocolsEngine(workspace_path=tmp_path)
    protocols = engine.list_protocols()
    assert len(protocols) >= 4
    names = [p["name"] for p in protocols]
    assert "workshop" in names
    assert "clean_slate" in names
    assert "lockdown" in names
    assert "overdrive" in names

    # Test clean_slate protocol
    scratch_dir = tmp_path / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    (scratch_dir / "temp.txt").write_text("junk data", encoding="utf-8")

    res_clean = engine.execute_protocol("clean_slate")
    assert res_clean["status"] == "ok"
    assert "Clean Slate" in res_clean["message"]
    assert not (scratch_dir / "temp.txt").exists()

    # Test unknown protocol
    res_err = engine.execute_protocol("unknown_protocol_xyz")
    assert res_err["status"] == "error"


def test_workspace_sentinel_code_anomaly_detection(tmp_path):
    sentinel = WorkspaceSentinel(workspace_path=str(tmp_path))
    assert sentinel.co_pilot_enabled is True

    # Create a broken Python file with a syntax error
    bad_code_file = tmp_path / "broken_script.py"
    bad_code_file.write_text("def broken_func(\n   return 1\n", encoding="utf-8")

    # Mock git status to report broken_script.py as modified
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = " M broken_script.py\n"
        mock_run.return_value = mock_proc

        events = sentinel.scan_for_code_anomalies()
        assert len(events) >= 1
        anom = events[0]
        assert anom.event_type == "CODE_ANOMALY"
        assert anom.details["anomaly_type"] == "SYNTAX_ERROR"
        assert anom.details["file"] == "broken_script.py"

    # Test merge conflict detection
    conflict_file = tmp_path / "conflict.py"
    conflict_file.write_text(
        "<<<<<<< HEAD\nx = 1\n=======\nx = 2\n>>>>>>> branch\n",
        encoding="utf-8"
    )
    with patch("subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = " M conflict.py\n"
        mock_run.return_value = mock_proc

        conflict_events = sentinel.scan_for_code_anomalies()
        assert len(conflict_events) >= 1
        assert any(e.details.get("anomaly_type") == "MERGE_CONFLICT" for e in conflict_events)

    # Test toggling co-pilot
    assert sentinel.toggle_copilot(False) is False
    assert sentinel.get_status()["co_pilot_enabled"] is False
    assert sentinel.toggle_copilot(True) is True
    assert sentinel.get_status()["co_pilot_enabled"] is True


@pytest.mark.asyncio
async def test_tool_registry_stark_briefing_and_protocols():
    reg = ToolRegistry()
    assert "get_stark_briefing" in reg.tools
    assert "execute_house_protocol" in reg.tools
    assert "toggle_sentinel_copilot" in reg.tools

    res_briefing = await reg.execute("get_stark_briefing", {})
    assert "Atmosphere:" in res_briefing

    res_copilot = await reg.execute("toggle_sentinel_copilot", {"enabled": True})
    assert "ACTIVATED" in res_copilot
