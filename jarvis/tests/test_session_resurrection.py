import pytest
import os
import tempfile
import asyncio
from unittest.mock import MagicMock

from jarvis.memory import Memory
from jarvis.api_client import JarvisAPIClient


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass


def test_anti_resurrection_get_session_and_switch(temp_db):
    """
    FIX 3 Regression Test:
    1. Create a session, save messages, and then delete it.
    2. Confirm it is removed from persistent storage and list_sessions().
    3. Attempt to fetch it via api_client.get_session(deleted_id).
    4. Assert api_client.get_session(deleted_id) returns None and does NOT auto-create a session.
    5. Assert deleted session does not reappear in list_sessions() or memory cache.
    """
    mem = Memory(db_path=temp_db)
    api_client = JarvisAPIClient(db_path=temp_db)

    # 1. Create session
    sess = api_client.new_session(title="To Be Deleted")
    deleted_id = sess.session_id
    api_client.add_user_message("Hello world", session_id=deleted_id)

    assert api_client.session_exists(deleted_id) is True
    assert mem.session_exists(deleted_id) is True

    # 2. Delete session
    del_ok = api_client.delete_session(deleted_id)
    assert del_ok is True
    assert mem.session_exists(deleted_id) is False
    assert api_client.session_exists(deleted_id) is False

    # 3. Attempt get_session with deleted session ID
    resurrect_attempt = api_client.get_session(deleted_id)
    assert resurrect_attempt is None  # Must NOT auto-create/resurrect!

    # 4. Confirm deleted ID is not in list_sessions
    all_sessions = api_client.list_sessions()
    all_ids = [s["session_id"] for s in all_sessions]
    assert deleted_id not in all_ids


def test_delete_session_failure_path(temp_db):
    """
    FIX 2 / FIX 4 Regression Test:
    1. Create a valid session in DB.
    2. Mock Memory.delete_session to return False (simulating write lock or failure).
    3. Perform delete_session.
    4. Verify delete_session returns False and session persists in storage.
    """
    mem = Memory(db_path=temp_db)
    api_client = JarvisAPIClient(db_path=temp_db)

    sess = api_client.new_session(title="Indestructible Session")
    sid = sess.session_id

    # Mock delete_session failure
    original_delete = mem.delete_session
    try:
        mem.delete_session = MagicMock(return_value=False)
        
        # Call api_client.delete_session with mocked memory failure
        # Replace internal Memory call with mocked instance
        from jarvis.memory import Memory as MemoryClass
        orig_init = MemoryClass.__init__

        def mock_mem_init(self_obj, db_path=None):
            orig_init(self_obj, db_path=temp_db)
            self_obj.delete_session = MagicMock(return_value=False)

        MemoryClass.__init__ = mock_mem_init
        try:
            success = api_client.delete_session(sid)
            assert success is False
        finally:
            MemoryClass.__init__ = orig_init

        # Verify session still exists in DB
        assert mem.session_exists(sid) is True
    finally:
        mem.delete_session = original_delete
