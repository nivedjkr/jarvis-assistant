"""
Tests for Mark 5.9 Multi-Agent Persona Fleet & Doctor Diagnostic Suite.
"""

import pytest
from jarvis.agents_registry import get_agents_registry, AgentsRegistry
from jarvis.doctor import JarvisDoctor
from jarvis.cli import JarvisAssistant


def test_agents_registry_builtins_and_switching():
    reg = get_agents_registry()
    agents = reg.list_agents()
    agent_ids = [a.agent_id for a in agents]

    # Verify all 5 built-in personas exist
    for expected in ["jarvis", "ultron", "friday", "edith", "karen"]:
        assert expected in agent_ids, f"Agent '{expected}' missing from registry"

    # Verify active agent switching
    ok = reg.set_active_agent("ultron")
    assert ok is True
    active = reg.get_active_agent()
    assert active.agent_id == "ultron"
    assert active.name == "ULTRON"

    # Switch back to jarvis
    reg.set_active_agent("jarvis")
    active_jarvis = reg.get_active_agent()
    assert active_jarvis.agent_id == "jarvis"


def test_agents_registry_custom_agent_lifecycle():
    reg = get_agents_registry()
    custom = reg.add_agent(
        agent_id="visionary",
        name="VISIONARY",
        role="Creative Design Architect",
        description="Generates visual layouts and design systems",
        emoji="✨"
    )
    assert custom.agent_id == "visionary"
    assert reg.get_agent("visionary") is not None

    # Delete custom agent
    deleted = reg.delete_agent("visionary")
    assert deleted is True
    assert reg.get_agent("visionary") is None


def test_jarvis_doctor_suite():
    doc = JarvisDoctor(fix=False)
    report = doc.run_all()
    assert len(report.findings) >= 8
    assert report.ok_count >= 7
    categories = {f.category for f in report.findings}
    assert "Runtime" in categories
    assert "Dependencies" in categories
    assert "Storage" in categories
    assert "Security" in categories
    assert "Agents" in categories


@pytest.mark.asyncio
async def test_cli_agents_and_doctor_slash_commands():
    app = JarvisAssistant(show_banner=False)

    # 1. /agents
    res_agents = await app.process("/agents")
    assert "JARVIS Multi-Agent Fleet" in res_agents or "Agent ID" in res_agents

    # 2. /agent switch friday
    res_switch = await app.process("/agent switch friday")
    assert "F.R.I.D.A.Y." in res_switch
    assert app.agent.agent_id == "friday"

    # 3. /agent info friday
    res_info = await app.process("/agent info friday")
    assert "F.R.I.D.A.Y." in res_info

    # 4. Switch back to jarvis
    res_back = await app.process("/agent switch jarvis")
    assert "J.A.R.V.I.S." in res_back
    assert app.agent.agent_id == "jarvis"

    # 5. /doctor
    res_doc = await app.process("/doctor")
    assert "Audit Complete" in res_doc
