import pytest
import os
import asyncio
from jarvis.tools import ToolRegistry

@pytest.fixture
def registry():
    return ToolRegistry()

def test_inspect_project(registry):
    res = asyncio.run(registry.execute("inspect_project", {"path": "."}))
    assert "<untrusted_external_content source='inspect_project'>" in res
    assert "Project Structure Overview" in res
    assert "Detected Languages/Frameworks" in res
    assert "Entry Points" in res
    assert "Test Files" in res

def test_run_tests(registry):
    # Run a specific passing test module
    res = asyncio.run(registry.execute("run_tests", {"path": ".", "pattern": "jarvis/tests/test_config.py"}))
    assert "<untrusted_external_content source='run_tests'>" in res
    assert "Status: PASSED" in res
    assert "Exit Code: 0" in res

def test_run_project_infer(registry):
    res = asyncio.run(registry.execute("run_project", {"path": "."}))
    assert "<untrusted_external_content source='run_project'>" in res
    assert "STDOUT:" in res

def test_run_project_explicit_command(registry):
    res = asyncio.run(registry.execute("run_project", {"command": "python --version", "path": "."}))
    assert "<untrusted_external_content source='run_project'>" in res
    assert "Exit Code 0" in res

def test_dependency_scan(registry):
    res = asyncio.run(registry.execute("dependency_scan", {"path": "."}))
    assert "<untrusted_external_content source='dependency_scan'>" in res

def test_secret_scan(registry):
    res = asyncio.run(registry.execute("secret_scan", {"path": "."}))
    assert "Secret Scan" in res

def test_sandbox_path_security_denied(registry):
    res = asyncio.run(registry.execute("inspect_project", {"path": "C:\\Windows"}))
    assert "ACCESS DENIED" in res or "resolves outside allowed directory roots" in res
