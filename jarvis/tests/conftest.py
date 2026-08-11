import pytest
import os
import sys

# Ensure repository root is on Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture
def tools():
    from jarvis.tools import ToolRegistry
    return ToolRegistry()

@pytest.fixture
def config():
    from jarvis.config_manager import ConfigManager
    return ConfigManager()

@pytest.fixture
def memory():
    from jarvis.memory import Memory
    return Memory()
