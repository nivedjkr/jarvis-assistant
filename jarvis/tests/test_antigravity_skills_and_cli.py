import os
import pytest
from pathlib import Path
from jarvis.skills_engine import SkillsEngine, get_skills_engine
from jarvis.tools import ToolRegistry, validate_tool_schemas
from jarvis.cli import JarvisAssistant
from jarvis.agents.coding_agent import CODING_TOOLS


def test_skills_engine_discovery():
    """Verify that all embedded Antigravity skills are discovered and parsed."""
    engine = get_skills_engine()
    skills = engine.list_skills()
    assert len(skills) >= 11, f"Expected at least 11 skills, got {len(skills)}"
    
    skill_names = {s["name"] for s in skills}
    expected = {
        "antigravity-guide",
        "agy-customizations",
        "google-antigravity-sdk",
        "android-cli",
        "permissioned-github",
        "generative_ui",
        "migrate-workflows",
        "agentic-coding",
        "subagent-orchestrator",
        "system-automation",
        "web-research"
    }
    assert expected.issubset(skill_names), f"Missing skills: {expected - skill_names}"


def test_skills_engine_activate_and_progressive_disclosure():
    """Verify skill activation and prompt XML generation."""
    engine = get_skills_engine()
    
    # Test activate
    content = engine.activate_skill("agentic-coding")
    assert "# Activated Skill: agentic-coding" in content
    assert "Verified Debug Loop" in content
    
    # Test non-existent skill
    missing = engine.activate_skill("non-existent-skill-xyz")
    assert "Error: Skill" in missing
    
    # Test prompt formatting
    xml = engine.format_prompt_skills_xml()
    assert "<skills>" in xml
    assert "</skills>" in xml
    assert "antigravity-guide:" in xml


def test_skills_engine_dynamic_creation(tmp_path):
    """Verify dynamic skill learning and persistence."""
    custom_dir = tmp_path / "skills"
    custom_dir.mkdir()
    engine = SkillsEngine(skills_dirs=[str(custom_dir)])
    
    res = engine.create_skill(
        name="test-custom-skill",
        description="A test skill for automated testing.",
        instructions="Step 1: Test.\nStep 2: Pass.",
        category="testing"
    )
    assert "Successfully created" in res
    assert "test-custom-skill" in engine.skills
    
    activated = engine.activate_skill("test-custom-skill")
    assert "Step 1: Test." in activated


def test_tool_registry_schemas_and_registration():
    """Verify that all Antigravity tools are registered and schemas validate."""
    registry = ToolRegistry()
    assert validate_tool_schemas(registry) is True
    
    antigravity_tools = [
        "view_file",
        "replace_file_content",
        "list_skills",
        "activate_skill",
        "learn_skill",
        "invoke_subagent",
        "list_subagents",
        "ask_question",
        "schedule_task"
    ]
    for t in antigravity_tools:
        assert t in registry.tools, f"Tool '{t}' is missing from ToolRegistry"


@pytest.mark.asyncio
async def test_view_file_tool(tmp_path):
    """Test view_file slicing and line numbers."""
    registry = ToolRegistry()
    
    # Create test file within workspace
    test_file = Path("jarvis/data/test_view_file.txt")
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("line 1\nline 2\nline 3\nline 4\nline 5\n", encoding="utf-8")
    
    try:
        # Full view
        res = await registry.execute("view_file", {"path": str(test_file)})
        assert "Showing lines 1 to 5" in res
        assert "1: line 1" in res
        assert "5: line 5" in res
        
        # Sliced view
        res_slice = await registry.execute("view_file", {
            "path": str(test_file),
            "start_line": 2,
            "end_line": 4
        })
        assert "Showing lines 2 to 4" in res_slice
        assert "2: line 2" in res_slice
        assert "4: line 4" in res_slice
        assert "1: line 1" not in res_slice
        assert "5: line 5" not in res_slice
    finally:
        if test_file.exists():
            test_file.unlink()


@pytest.mark.asyncio
async def test_replace_file_content_tool():
    """Test surgical chunk search and replace."""
    registry = ToolRegistry()
    test_file = Path("jarvis/data/test_replace_chunk.txt")
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def hello():\n    return 'old'\n", encoding="utf-8")
    
    try:
        res = await registry.execute("replace_file_content", {
            "path": str(test_file),
            "target_content": "return 'old'",
            "replacement_content": "return 'new'"
        })
        assert "Successfully updated" in res
        content = test_file.read_text(encoding="utf-8")
        assert "return 'new'" in content
        assert "return 'old'" not in content
    finally:
        if test_file.exists():
            test_file.unlink()


@pytest.mark.asyncio
async def test_security_sandboxing_on_new_tools():
    """Verify that view_file and replace_file_content respect security sandboxing."""
    registry = ToolRegistry()
    
    # Blocked pattern check (.env)
    res = await registry.execute("view_file", {"path": ".env"})
    assert "ACCESS DENIED" in res
    
    # Outside root check
    res_outside = await registry.execute("view_file", {"path": "C:/Windows/System32/drivers/etc/hosts"})
    assert "ACCESS DENIED" in res_outside


def test_coding_agent_tools_coverage():
    """Verify that CodingAgent has access to Antigravity tools."""
    for tool in ["view_file", "replace_file_content", "list_skills", "activate_skill", "learn_skill"]:
        assert tool in CODING_TOOLS, f"Tool '{tool}' missing from CODING_TOOLS"


@pytest.mark.asyncio
async def test_cli_slash_commands():
    """Test Antigravity slash commands in CLI."""
    app = JarvisAssistant()
    
    # /skills
    res_skills = await app.process("/skills")
    assert "/skill <name>" in res_skills
    
    # /skill agentic-coding
    res_skill = await app.process("/skill agentic-coding")
    assert "Loaded skill 'agentic-coding'" in res_skill
    
    # /subagents
    res_agents = await app.process("/subagents")
    assert "Subagent fleet ready" in res_agents
    
    # /mode boost
    res_mode = await app.process("/mode boost")
    assert app.mode == "boost"
    assert "BOOST" in res_mode
    
    # /help
    res_help = await app.process("/help")
    assert "/skills" in res_help
    assert "ANTIGRAVITY" in res_help
