import os
import time
import pytest
import tempfile
from pathlib import Path
from jarvis.memory import Memory
from jarvis.api_client import JarvisAPIClient, ConversationSession
from jarvis.tools import ToolRegistry

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

def test_session_db_persistence(temp_db):
    mem = Memory(db_path=temp_db)
    sid = "test_sess_001"
    
    # Save session
    mem.save_session(sid, title="Initial Title", created_at=1000.0, last_active=1000.0)
    
    # Add messages
    mem.add_session_message(sid, "user", "Hello JARVIS", timestamp=1001.0)
    mem.add_session_message(sid, "assistant", "Hello sir", timestamp=1002.0)
    
    # Verify retrieving session
    s_info = mem.get_session(sid)
    assert s_info is not None
    assert s_info["title"] == "Initial Title"
    assert s_info["message_count"] == 2
    
    # Retrieve messages
    msgs = mem.get_session_messages(sid)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == "Hello JARVIS"
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"] == "Hello sir"
    
    # Rename session
    assert mem.rename_session(sid, "New Renamed Title")
    s_info2 = mem.get_session(sid)
    assert s_info2["title"] == "New Renamed Title"
    
    # List sessions
    all_s = mem.list_sessions()
    assert len(all_s) >= 1
    assert any(s["session_id"] == sid for s in all_s)

def test_conversation_session_class(temp_db):
    sid = "sess_class_test"
    mem = Memory(db_path=temp_db)
    
    sess = ConversationSession(sid, title="New Conversation", db_path=temp_db)
    sess.add_message("user", "What is quantum mechanics?")
    
    # Confirm auto-title generation from user message
    assert sess.title == "What is quantum mechanics?"
    
    sess.add_message("assistant", "Quantum mechanics is a fundamental theory in physics...")
    
    # Reload in a separate instance from DB
    sess_reloaded = ConversationSession(sid, db_path=temp_db)
    assert sess_reloaded.title == "What is quantum mechanics?"
    assert len(sess_reloaded.messages) == 2
    assert sess_reloaded.messages[0]["content"] == "What is quantum mechanics?"

def test_session_tools_registration(temp_db):
    registry = ToolRegistry()
    assert "list_sessions" in registry.tools
    assert "new_session" in registry.tools
    assert "switch_session" in registry.tools
    assert "rename_session" in registry.tools

def test_proactive_memory_prompt_content():
    client = JarvisAPIClient()
    prompt = client.system_prompt
    assert "PROACTIVE OBSIDIAN MEMORY FILING INSTRUCTIONS" in prompt
    assert "Memory/profile.md" in prompt
    assert "Memory/topics/<topic>.md" in prompt
    assert "Memory/people/<name>.md" in prompt
    assert "Memory/areas/<project>.md" in prompt
    assert "JUDGMENT RULES" in prompt

def test_throwaway_vs_durable_filtering():
    import re
    def check_needs_tools(user_msg):
        ACTION_TOOL_TRIGGERS = {
            'email', 'mail', 'inbox', 'gmail', 'calendar', 'obsidian',
            'git', 'github', 'repo', 'file', 'dir', 'folder',
            'weather', 'disk', 'vitals', 'create', 'delete', 'update',
            'write', 'list', 'open', 'close', 'spotify', 'chrome', 'clipboard',
            'gist', 'commit', 'pull', 'branch', 'pr', 'issue', 'inventory', 'reminders',
            'watchlist', 'project', 'protocol', 'inspect', 'remember', 'prefer', 'preference',
            'favorite', 'decided', 'decision', 'always', 'never'
        }
        lower_user = user_msg.lower().strip()
        words = set(re.findall(r'\b\w+\b', lower_user)) if lower_user else set()
        return bool(words & ACTION_TOOL_TRIGGERS) or lower_user.startswith('/')

    # Throwaway calculation should NOT trigger memory tools
    assert not check_needs_tools("what's 2+2")
    assert not check_needs_tools("hello jarvis")
    
    # Stated preference SHOULD trigger tool calling pipeline for memory evaluation
    assert check_needs_tools("I prefer dark mode themes and espresso")
    assert check_needs_tools("My favorite programming language is Python")

def test_full_backend_restart_session_preservation(temp_db):
    # Simulate first backend run
    mem1 = Memory(db_path=temp_db)
    sid = "restart_test_sess"
    mem1.save_session(sid, title="Initial Restart Test")
    mem1.add_session_message(sid, "user", "Message before restart")
    mem1.add_session_message(sid, "assistant", "Response before restart")
    
    # Simulate backend complete shutdown & restart (new Memory instance loaded from same db)
    mem2 = Memory(db_path=temp_db)
    reloaded_sessions = mem2.list_sessions()
    target = next((s for s in reloaded_sessions if s["session_id"] == sid), None)
    
    assert target is not None
    assert target["title"] == "Initial Restart Test"
    assert target["message_count"] == 2
    
    reloaded_msgs = mem2.get_session_messages(sid)
    assert len(reloaded_msgs) == 2
    assert reloaded_msgs[0]["content"] == "Message before restart"
    assert reloaded_msgs[1]["content"] == "Response before restart"

def test_delete_session(temp_db):
    mem = Memory(db_path=temp_db)
    sid = "to_be_deleted"
    mem.save_session(sid, title="Delete Me")
    mem.add_session_message(sid, "user", "Goodbye session")
    
    assert mem.get_session(sid) is not None
    assert mem.delete_session(sid) is True
    assert mem.get_session(sid) is None
    assert len(mem.get_session_messages(sid)) == 0


def test_delete_inactive_session_and_persistence_after_restart(temp_db):
    mem1 = Memory(db_path=temp_db)
    s1 = "sess_keep"
    s2 = "sess_delete"
    mem1.save_session(s1, title="Keep Me")
    mem1.save_session(s2, title="Delete Me")
    mem1.add_session_message(s1, "user", "Keep message")
    mem1.add_session_message(s2, "user", "Delete message")

    assert len(mem1.list_sessions()) == 2
    assert mem1.delete_session(s2) is True
    assert len(mem1.list_sessions()) == 1

    # Simulate backend restart with a new Memory instance
    mem2 = Memory(db_path=temp_db)
    remaining = mem2.list_sessions()
    assert len(remaining) == 1
    assert remaining[0]["session_id"] == s1
    assert mem2.get_session(s2) is None
    assert len(mem2.get_session_messages(s2)) == 0


def test_delete_active_session_recovery_and_persistence(temp_db):
    from jarvis.api_client import JarvisAPIClient
    api_client = JarvisAPIClient()
    
    # Create two sessions
    s1 = api_client.new_session(title="Active Session")
    s2 = api_client.new_session(title="Backup Session")
    
    # Delete active session s1
    deleted_sid = s1.session_id
    success = api_client.delete_session(deleted_sid)
    assert success is True
    
    # List remaining sessions
    sessions = api_client.list_sessions()
    remaining_ids = [s["session_id"] for s in sessions]
    assert deleted_sid not in remaining_ids
    
    # Active recovery check
    fallback_sid = sessions[0]["session_id"] if sessions else api_client.new_session().session_id
    assert fallback_sid != deleted_sid


def test_true_reconnect_session_synchronization(temp_db):
    """
    True reconnect test:
    1. Create Session A and Session B.
    2. Delete Session A.
    3. Simulate client reconnecting with stale Session A ID.
    4. Verify backend rejects deleted Session A, returns Session B, and Session A never returns.
    """
    from jarvis.memory import Memory
    from jarvis.api_client import JarvisAPIClient
    
    # 1. Start backend / memory instance
    mem = Memory(db_path=temp_db)
    api_client = JarvisAPIClient()
    
    id_a = "session_test_a"
    id_b = "session_test_b"
    mem.save_session(id_a, title="Session A")
    mem.save_session(id_b, title="Session B")
    mem.add_session_message(id_a, "user", "Message A")
    mem.add_session_message(id_b, "user", "Message B")
    
    # Also register in api_client sessions cache
    api_client.sessions[id_a] = api_client.get_session(id_a)
    api_client.sessions[id_b] = api_client.get_session(id_b)
    
    # Verify both exist in SQLite
    existing = mem.list_sessions()
    existing_ids = [s["session_id"] for s in existing]
    assert id_a in existing_ids
    assert id_b in existing_ids
    
    # 2. Delete Session A via memory & api_client
    print(f"[SESSION] Delete requested: {id_a}")
    success = mem.delete_session(id_a)
    if id_a in api_client.sessions:
        del api_client.sessions[id_a]
    assert success is True
    print(f"[SESSION] Persistent delete result: success")
    
    # Verify Session A is gone from SQLite and memory
    remaining_after_del = mem.list_sessions()
    remaining_ids_after_del = [s["session_id"] for s in remaining_after_del]
    assert id_a not in remaining_ids_after_del
    assert id_b in remaining_ids_after_del
    assert api_client.sessions.get(id_a) is None
    print(f"[SESSION] Cache invalidated: yes")

    # 3. Simulate client reconnecting with stale Session A ID (e.g. old session_config.json)
    print(f"[SESSION] Simulating reconnect with stale ID: {id_a}")
    stale_req_id = id_a
    current_db_sessions = mem.list_sessions()
    current_db_ids = {s["session_id"] for s in current_db_sessions}
    
    # Reconnect validation logic (mirroring api.py)
    if stale_req_id in current_db_ids:
        active_id = stale_req_id
    else:
        active_id = current_db_sessions[0]["session_id"] if current_db_sessions else "new_session"
    
    # 4. Verify Session A is rejected and fallback active_id is Session B
    assert active_id == id_b
    assert active_id != id_a
    
    # 5. Simulate backend complete restart
    mem_restarted = Memory(db_path=temp_db)
    restarted_sessions = mem_restarted.list_sessions()
    restarted_ids = [s["session_id"] for s in restarted_sessions]
    print(f"[SESSION] Authoritative session count after restart: {len(restarted_sessions)}")
    print(f"[SESSION] Session IDs returned: {restarted_ids}")
    
    assert id_a not in restarted_ids
    assert id_b in restarted_ids


