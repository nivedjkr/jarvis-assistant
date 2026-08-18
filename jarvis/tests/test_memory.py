import pytest
from jarvis.memory import list_all_facts, delete_fact, edit_fact, get_memory_stats

def test_save_and_retrieve_fact(memory):
    memory.log_fact("test fact content", category="test_category")
    facts = list_all_facts("test_category")
    assert any("test fact content" in f['content'] for f in facts)

def test_delete_fact(memory):
    memory.log_fact("deletable fact content", category="test")
    facts = list_all_facts("test")
    assert facts, "Expected facts to be populated"
    fact_id = facts[0]['id']
    result = delete_fact(fact_id)
    assert "deleted" in result.lower()

def test_memory_stats(memory):
    stats = get_memory_stats()
    assert "total_facts" in stats
    assert isinstance(stats["total_facts"], int)

def test_get_reminders_status(memory):
    memory.add_reminder("Buy milk")
    reminders = memory.get_reminders(status="pending")
    assert len(reminders) >= 1
    assert any(r["text"] == "Buy milk" for r in reminders)

