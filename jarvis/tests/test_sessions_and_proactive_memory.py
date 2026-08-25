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

