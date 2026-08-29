import pytest
from jarvis.api_client import JarvisAPIClient

def test_api_client_init():
    client = JarvisAPIClient()
    assert client.provider is not None
    assert client.system_prompt is not None

def test_api_client_session():
    client = JarvisAPIClient()
    session = client.new_session(session_id="test_session")
    assert session.session_id == "test_session"
    fetched = client.get_session("test_session")
    assert fetched is not None
    assert fetched.session_id == "test_session"
