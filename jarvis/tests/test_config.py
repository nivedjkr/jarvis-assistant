import pytest

def test_config_loads(config):
    assert config.config is not None

def test_config_get_default(config):
    val = config.get("nonexistent.key", "default")
    assert val == "default"

def test_config_set_and_get(config):
    config.set("test.key", "test_value")
    assert config.get("test.key") == "test_value"
