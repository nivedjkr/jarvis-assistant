import pytest
from pathlib import Path
from jarvis.semantic_memory import SemanticMemory
from jarvis.tools import ToolRegistry, validate_tool_schemas


def test_hierarchical_memory_isolated_lifecycle(tmp_path):
    """Test memory initialization with isolated storage."""
    idx_path = tmp_path / "test_idx.faiss"
    facts_path = tmp_path / "test_facts.json"
    
    mem = SemanticMemory(index_path=str(idx_path), facts_path=str(facts_path))
    assert mem.facts == []
    
    # Add hierarchical facts
    res1 = mem.add_fact(
        fact="The user prefers dark mode and concise responses.",
        category="profile",
        tags=["ui", "preferences"]
    )
    assert "Hierarchical fact stored [profile]" in res1
    
    res2 = mem.add_fact(
        fact="JARVIS Mk 5.4 introduces unified autonomous intelligence.",
        category="project",
        project_id="jarvis",
        tags=["release", "ai"]
    )
    assert "Hierarchical fact stored [project]" in res2
    
    # Verify persistence files
    assert idx_path.exists()
    assert facts_path.exists()
    assert len(mem.facts) == 2


def test_hierarchical_memory_filtering(tmp_path):
    """Test semantic search with category and project metadata filters."""
    mem = SemanticMemory(
        index_path=str(tmp_path / "filt_idx.faiss"),
        facts_path=str(tmp_path / "filt_facts.json")
    )
    
    mem.add_fact("Python asyncio keeps the backend responsive.", category="topic", tags=["python"])
    mem.add_fact("The client requires dark theme.", category="profile", tags=["ui"])
    mem.add_fact("Deploy JARVIS to AWS ECS cluster.", category="project", project_id="cloud-deploy")

    # Unfiltered search
    all_res = mem.search("Python backend", top_k=3)
    assert len(all_res) >= 1
    
    # Category filter
    prof_res = mem.search("Python", category="profile", top_k=3)
    for r in prof_res:
        assert r["category"] == "profile"
        
    # Project filter
    proj_res = mem.search("Deploy", project_id="cloud-deploy", top_k=3)
    assert len(proj_res) >= 1
    assert proj_res[0]["project_id"] == "cloud-deploy"


def test_hierarchical_context_formatting(tmp_path):
    """Test context string generation with hierarchical labels."""
    mem = SemanticMemory(
        index_path=str(tmp_path / "ctx_idx.faiss"),
        facts_path=str(tmp_path / "ctx_facts.json")
    )
    mem.add_fact("NVIDIA NIM provides ultra fast 120B inference.", category="topic", project_id="jarvis")
    
    ctx = mem.get_relevant_context("NVIDIA NIM inference")
    assert "Hierarchical Memory Context:" in ctx
    assert "[TOPIC]" in ctx
    assert "(jarvis)" in ctx


def test_obsidian_vault_indexing(tmp_path):
    """Test simulated Obsidian vault indexing with header chunking and category inference."""
    vault = tmp_path / "test_vault"
    vault.mkdir()
    (vault / "profile.md").write_text("# User Profile\nNived is an AI engineer building JARVIS.", encoding="utf-8")
    
    topics_dir = vault / "Memory" / "topics"
    topics_dir.mkdir(parents=True)
    (topics_dir / "agents.md").write_text("# Autonomous Agents\n## Core Principles\nAgents reason and act with tools.", encoding="utf-8")

    mem = SemanticMemory(
        index_path=str(tmp_path / "obs_idx.faiss"),
        facts_path=str(tmp_path / "obs_facts.json")
    )
    res = mem.index_obsidian_vault(vault_path=str(vault))
    assert res["status"] == "success"
    assert res["notes_scanned"] == 2
    assert res["chunks_indexed"] >= 2
    assert len(mem.facts) >= 2


@pytest.mark.asyncio
async def test_hierarchical_memory_tools():
    """Verify ToolRegistry registration and execution for hierarchical memory tools."""
    registry = ToolRegistry()
    assert validate_tool_schemas(registry) is True
    
    for tool_name in ["search_hierarchical_memory", "store_contextual_memory", "index_obsidian_vault"]:
        assert tool_name in registry.tools, f"Tool '{tool_name}' missing from ToolRegistry"

    # Test store_contextual_memory execution
    store_res = await registry.execute("store_contextual_memory", {
        "text": "Automated tests must pass with 100% verification.",
        "category": "topic",
        "tags": ["testing", "verification"]
    })
    assert "Hierarchical fact stored" in store_res

    # Test search_hierarchical_memory execution
    search_res = await registry.execute("search_hierarchical_memory", {
        "query": "verification tests",
        "category": "topic"
    })
    assert "score:" in search_res
