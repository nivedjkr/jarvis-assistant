"""
Automated Ground-Truth Verification for SWE Features Phase 2
"""
import sys
import os
import shutil
import asyncio
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

root_dir = str(Path(__file__).resolve().parents[3])
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

print("Testing Software Engineer Features (Phase 2)...\n")

from jarvis.cli import JARVISCLI

cli = JARVISCLI()

async def run_swe_tests():
    # -------------------------------------------------------------
    # 1. Git Awareness Tool
    # -------------------------------------------------------------
    print("--- 2.1 Git Awareness Tool ---")
    raw_git_res = await cli.tools.execute_tool("git_status", directory=".")
    print(f"✓ Raw Tool Output:\n{raw_git_res}\n")
    assert "Branch:" in raw_git_res or "branch" in raw_git_res.lower()

    git_res = await cli.process_command("what's my git status")
    print(f"✓ AI Summary Output:\n{git_res}\n")
    assert any(k in git_res.lower() for k in ["branch", "git", "status", "main", "origin"])

    # -------------------------------------------------------------
    # 2. Error Explainer
    # -------------------------------------------------------------
    print("--- 2.2 Error Explainer Tool ---")
    err_text = "ZeroDivisionError: division by zero in calculate_rate() at line 42"
    explain_res = await cli.process_command(f"/explain-error {err_text}")
    print(f"✓ Output:\n{explain_res[:300]}...\n")
    assert len(explain_res) > 20

    # -------------------------------------------------------------
    # 3. Project Switcher (Protocol-based)
    # -------------------------------------------------------------
    print("--- 2.3 Project Switcher (Protocol-based) ---")
    proj_dir = Path("test_project_workspace").resolve()
    proj_dir.mkdir(parents=True, exist_ok=True)
    
    todo_path = proj_dir / "TODO.md"
    with open(todo_path, "w", encoding="utf-8") as f:
        f.write("# Project TODOs\n- [ ] Implement trade journal\n- [x] Implement SWE features")

    # Register project protocol
    cli.protocol_manager.add_protocol(
        name="test_project",
        description="Switch to test project workspace",
        steps=[],
        project_path=str(proj_dir),
        venv_path=None
    )

    original_cwd = os.getcwd()
    try:
        switch_res = await cli.protocol_manager.execute_protocol("test_project", cli.tools)
        print(f"✓ Output:\n{switch_res}\n")
        assert "Switched directory" in switch_res
        assert "TODO.md Content" in switch_res
    finally:
        os.chdir(original_cwd)
        if proj_dir.exists():
            shutil.rmtree(proj_dir)

asyncio.run(run_swe_tests())

print("All Software Engineer Features (Phase 2) tests PASSED successfully!")
