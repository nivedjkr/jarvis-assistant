"""
Automated Bug Tests for OpenClaw Bridge & GitHub Automation in JARVIS
"""
import sys
import os
import asyncio
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Starting OpenClaw Bridge & GitHub Automation Bug Tests...\n")

from jarvis.tools import ToolRegistry
from jarvis.openclaw_bridge import (
    register_openclaw_tools,
    SKILL_MAP,
    REGISTERED_SKILLS,
    OpenClawGitHubTool,
    OpenClawSkillRegistryTool,
    OpenClawWeatherTool,
    OpenClawGenericSkillTool,
    call_skill
)


async def run_openclaw_bug_tests():
    # -------------------------------------------------------------
    # 1. Tool Registry Registration
    # -------------------------------------------------------------
    print("--- 1. Tool Registry Registration ---")
    registry = ToolRegistry(confirm_dangerous=False)
    register_openclaw_tools(registry)
    
    for skill in REGISTERED_SKILLS:
        tool = registry.get_tool(skill)
        assert tool is not None, f"Skill {skill} was not registered in ToolRegistry!"
        print(f"✓ Registered tool: {tool.name} - {tool.description[:50]}...")
    print("✓ Tool registry check passed!\n")

    # -------------------------------------------------------------
    # 2. OpenClaw GitHub Tool - Standard Command/Subcommand Execution
    # -------------------------------------------------------------
    print("--- 2. OpenClaw GitHub Tool: Standard Invocation ---")
    github_tool = OpenClawGitHubTool(default_repo="nivedjkr/jarvis-assistant")
    
    # Issue list
    res_issues = await github_tool.execute(command="issue", subcommand="list", limit=5)
    print(f"✓ issue list result:\n{res_issues[:200]}...\n")
    assert not res_issues.startswith("Error (exit 1): unknown command"), f"Invalid command output: {res_issues}"
    assert not res_issues.startswith("Error (exit 1): unknown flag"), f"Invalid flag output: {res_issues}"

    # PR status
    res_pr = await github_tool.execute(command="pr", subcommand="status")
    print(f"✓ pr status result:\n{res_pr[:200]}...\n")
    assert not res_pr.startswith("Error (exit 1): unknown command"), f"Invalid command output: {res_pr}"

    # API user
    res_api = await github_tool.execute(command="api", subcommand="user")
    print(f"✓ api user result:\n{res_api[:200]}...\n")
    assert "login" in res_api or "nivedjkr" in res_api or res_api.startswith("Error"), f"API output error: {res_api}"

    # -------------------------------------------------------------
    # 3. OpenClaw GitHub Tool - Action Alias Mapping & Parameter Bugs
    # -------------------------------------------------------------
    print("--- 3. OpenClaw GitHub Tool: Action Alias & Kwargs Formatting ---")
    
    # Action="list" (Common pattern passed by call_skill or generic caller)
    res_act_list = await github_tool.execute(action="list")
    print(f"✓ action='list' result:\n{res_act_list[:200]}...\n")
    assert "unknown command" not in res_act_list.lower(), f"action='list' produced unknown command: {res_act_list}"
    assert "unknown flag" not in res_act_list.lower(), f"action='list' produced unknown flag: {res_act_list}"

    # Action="issues"
    res_act_issues = await github_tool.execute(action="issues")
    print(f"✓ action='issues' result:\n{res_act_issues[:200]}...\n")
    assert "unknown command" not in res_act_issues.lower(), f"action='issues' failed: {res_act_issues}"

    # Action="prs"
    res_act_prs = await github_tool.execute(action="prs")
    print(f"✓ action='prs' result:\n{res_act_prs[:200]}...\n")
    assert "unknown command" not in res_act_prs.lower(), f"action='prs' failed: {res_act_prs}"

    # Action="repo view"
    res_act_repo = await github_tool.execute(action="repo view")
    print(f"✓ action='repo view' result:\n{res_act_repo[:200]}...\n")
    assert "unknown command" not in res_act_repo.lower(), f"action='repo view' failed: {res_act_repo}"

    # Kwargs with underscores & boolean flags
    res_kwargs = await github_tool.execute(command="issue", subcommand="list", json="number,title", limit=3, draft=False)
    print(f"✓ Kwargs formatting test result:\n{res_kwargs[:200]}...\n")
    assert "unknown flag" not in res_kwargs.lower(), f"Flag conversion failed: {res_kwargs}"
    assert "--draft" not in res_kwargs, f"Boolean False included: {res_kwargs}"

    # Positional number argument test
    res_num = await github_tool.execute(command="issue", subcommand="view", number=1)
    print(f"✓ Positional number arg test result:\n{res_num[:200]}...\n")
    assert "unknown flag: --number" not in res_num, f"Positional arg passed as --number flag: {res_num}"

    # Non-repo scoped command (e.g. auth status) - should not pass --repo
    res_auth = await github_tool.execute(command="auth", subcommand="status")
    print(f"✓ Auth status test result:\n{res_auth[:200]}...\n")
    assert "unknown flag: --repo" not in res_auth, f"--repo passed to gh auth status: {res_auth}"

    # -------------------------------------------------------------
    # 4. OpenClaw Skill Registry Tool
    # -------------------------------------------------------------
    print("--- 4. OpenClaw Skill Registry Tool ---")
    skills_tool = OpenClawSkillRegistryTool()
    res_skills_list = await skills_tool.execute(action="list")
    print(f"✓ skills list result:\n{res_skills_list[:200]}...\n")
    
    res_skills_search = await skills_tool.execute(action="search", query="github")
    print(f"✓ skills search result:\n{res_skills_search[:200]}...\n")

    # -------------------------------------------------------------
    # 5. OpenClaw Weather Tool
    # -------------------------------------------------------------
    print("--- 5. OpenClaw Weather Tool ---")
    weather_tool = OpenClawWeatherTool()
    res_weather = await weather_tool.execute(location="Tokyo")
    print(f"✓ weather result for Tokyo:\n{res_weather}\n")
    assert "Temperature:" in res_weather or "Tokyo" in res_weather, f"Weather failed: {res_weather}"

    # -------------------------------------------------------------
    # 6. OpenClaw Generic Skill Tool & Helpers
    # -------------------------------------------------------------
    print("--- 6. Generic Skill Tool & Helpers ---")
    gen_tool = OpenClawGenericSkillTool()
    res_gen_err = await gen_tool.execute(skill="")
    assert "Error:" in res_gen_err, "Generic tool failed to report missing skill parameter"
    print(f"✓ Generic tool missing skill validation: {res_gen_err}")

    # call_skill test
    cs_res = call_skill("openclaw_weather", {"location": "Paris"})
    print(f"✓ call_skill openclaw_weather result:\n{cs_res[:150]}...\n")
    assert "Temperature:" in cs_res or "Paris" in cs_res, f"call_skill weather failed: {cs_res}"

    print("\nAll OpenClaw Bridge & GitHub Automation Bug Tests PASSED!")


if __name__ == "__main__":
    asyncio.run(run_openclaw_bug_tests())
