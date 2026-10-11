"""
Test suite for Mark 5.7 Multi-Disk, Archive Orchestration, Overleaf & LaTeX Publishing,
and Proactive Problem-Solving Capabilities.
"""

import os
import zipfile
import tarfile
import pytest
from pathlib import Path
from jarvis.tools import ToolRegistry, validate_tool_schemas, _get_allowed_roots, _validate_sandbox_path
from jarvis.skills_engine import SkillsEngine, get_skills_engine
from jarvis.proactive_engine import RelevanceGate
from jarvis.cli import JarvisAssistant


def test_multi_disk_sandbox_resolution():
    """Verify that _get_allowed_roots discovers mounted partitions and enforces security sandboxing."""
    roots = _get_allowed_roots()
    assert len(roots) >= 1
    # Check that any system partition is included in lower-case normalized form
    assert any("c:" in r or "d:" in r for r in roots)

    # Denylist must block sensitive paths regardless of disk
    ok_win, err_win = _validate_sandbox_path("C:\\Windows\\System32\\notepad.exe")
    assert not ok_win
    assert "ACCESS DENIED" in err_win

    ok_env, err_env = _validate_sandbox_path(".env")
    assert not ok_env
    assert "ACCESS DENIED" in err_env


def test_tool_registry_schemas_and_new_tools():
    """Verify that ToolRegistry registers the new archive, Overleaf, and file tools with valid schemas."""
    reg = ToolRegistry()
    assert "inspect_and_edit_archive" in reg.tools
    assert "validate_latex_project" in reg.tools
    assert "prepare_overleaf_archive" in reg.tools
    assert "write_to_file" in reg.tools
    assert validate_tool_schemas(reg) is True


@pytest.mark.asyncio
async def test_inspect_and_edit_archive(tmp_path):
    """Test surgical viewing, replacing, adding, and deleting files inside a zip archive."""
    reg = ToolRegistry()
    test_zip = tmp_path / "test_project.zip"
    
    # Create initial zip
    with zipfile.ZipFile(test_zip, "w") as zf:
        zf.writestr("main.tex", "\\documentclass{article}\n\\begin{document}\nHello World\n\\end{document}\n")
        zf.writestr("notes.txt", "Initial notes\n")

    # 1. Action: view
    res_view = await reg.execute("inspect_and_edit_archive", {
        "archive_path": str(test_zip),
        "target_file_in_archive": "main.tex",
        "action": "view"
    })
    assert "Hello World" in res_view
    assert "main.tex" in res_view

    # 2. Action: replace content
    new_tex = "\\documentclass{article}\n\\begin{document}\nUpdated for Overleaf\n\\end{document}\n"
    res_replace = await reg.execute("inspect_and_edit_archive", {
        "archive_path": str(test_zip),
        "target_file_in_archive": "main.tex",
        "replacement_content": new_tex,
        "action": "replace"
    })
    assert "Successfully updated archive" in res_replace

    # Verify updated content in zip
    with zipfile.ZipFile(test_zip, "r") as zf:
        content = zf.read("main.tex").decode("utf-8")
        assert "Updated for Overleaf" in content

    # 3. Action: add a new file
    res_add = await reg.execute("inspect_and_edit_archive", {
        "archive_path": str(test_zip),
        "target_file_in_archive": "references.bib",
        "replacement_content": "@article{ref1, title={Test Paper}, author={Author}, year={2026}}\n",
        "action": "add"
    })
    assert "Successfully updated archive" in res_add

    with zipfile.ZipFile(test_zip, "r") as zf:
        assert "references.bib" in zf.namelist()

    # 4. Action: extract single file
    extract_target = tmp_path / "extracted_bib.bib"
    res_extract = await reg.execute("inspect_and_edit_archive", {
        "archive_path": str(test_zip),
        "target_file_in_archive": "references.bib",
        "destination_path": str(extract_target),
        "action": "extract_file"
    })
    assert "Successfully extracted" in res_extract
    assert extract_target.exists()
    assert "ref1" in extract_target.read_text(encoding="utf-8")

    # 5. Action: delete file
    res_del = await reg.execute("inspect_and_edit_archive", {
        "archive_path": str(test_zip),
        "target_file_in_archive": "notes.txt",
        "action": "delete"
    })
    assert "Successfully updated archive" in res_del

    with zipfile.ZipFile(test_zip, "r") as zf:
        assert "notes.txt" not in zf.namelist()


@pytest.mark.asyncio
async def test_validate_latex_project(tmp_path):
    """Test LaTeX and Overleaf project validation detecting missing assets, unclosed envs, and citations."""
    reg = ToolRegistry()
    proj_dir = tmp_path / "paper_project"
    proj_dir.mkdir()

    # Valid base
    main_tex = proj_dir / "main.tex"
    main_tex.write_text(
        "\\documentclass{article}\n"
        "\\usepackage{graphicx}\n"
        "\\begin{document}\n"
        "\\section{Introduction}\n"
        "Citing \\cite{author2026}.\n"
        "\\begin{figure}\n"
        "  \\includegraphics{figures/model.png}\n"
        "\\end{figure}\n"
        "\\bibliography{refs}\n"
        "\\end{document}\n",
        encoding="utf-8"
    )

    # Initial validation (missing figure, missing bib)
    res_warn = await reg.execute("validate_latex_project", {"project_path": str(proj_dir)})
    assert "LaTeX & Overleaf Project Validation Report" in res_warn
    assert "WARNINGS DETECTED" in res_warn or "CRITICAL ISSUES" in res_warn
    assert "figures/model.png" in res_warn
    assert "refs" in res_warn

    # Fix figure and bib
    figs_dir = proj_dir / "figures"
    figs_dir.mkdir()
    (figs_dir / "model.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    bib_file = proj_dir / "refs.bib"
    bib_file.write_text(
        "@article{author2026,\n"
        "  title={Agentic Systems},\n"
        "  author={Nived},\n"
        "  year={2026}\n"
        "}\n",
        encoding="utf-8"
    )

    res_clean = await reg.execute("validate_latex_project", {"project_path": str(proj_dir)})
    assert "PASSED (Ready for Overleaf)" in res_clean
    assert "All environment blocks balanced" in res_clean

    # Test unclosed environment
    bad_tex = proj_dir / "bad.tex"
    bad_tex.write_text(
        "\\documentclass{article}\n\\begin{document}\n\\begin{itemize}\n\\item Item 1\n\\end{document}\n",
        encoding="utf-8"
    )
    res_bad = await reg.execute("validate_latex_project", {"project_path": str(proj_dir)})
    assert "CRITICAL ISSUES" in res_bad or "Unclosed environment" in res_bad
    bad_tex.unlink()


@pytest.mark.asyncio
async def test_prepare_overleaf_archive(tmp_path):
    """Test packaging a LaTeX project into an Overleaf-ready clean zip with stripped clutter."""
    reg = ToolRegistry()
    source_dir = tmp_path / "my_latex_source"
    source_dir.mkdir()

    # Create source files and clutter
    (source_dir / "main.tex").write_text(
        "\\documentclass{article}\n\\begin{document}\n\\includegraphics{figs\\chart.png}\n\\end{document}\n",
        encoding="utf-8"
    )
    figs = source_dir / "figs"
    figs.mkdir()
    (figs / "chart.png").write_bytes(b"PNGDATA")

    # Add clutter files that should be stripped
    (source_dir / "main.aux").write_text("auxiliary", encoding="utf-8")
    (source_dir / "main.log").write_text("log data", encoding="utf-8")
    (source_dir / "main.bbl").write_text("bbl data", encoding="utf-8")
    (source_dir / ".DS_Store").write_bytes(b"junk")
    (source_dir / "Thumbs.db").write_bytes(b"junk")

    out_zip = tmp_path / "overleaf_bundle.zip"
    res = await reg.execute("prepare_overleaf_archive", {
        "source_path": str(source_dir),
        "output_archive_path": str(out_zip),
        "clean_artifacts": True
    })

    assert "Successfully created Overleaf-ready archive" in res
    assert out_zip.exists()

    with zipfile.ZipFile(out_zip, "r") as zf:
        namelist = zf.namelist()
        assert "main.tex" in namelist
        assert "figs/chart.png" in [n.replace("\\", "/") for n in namelist]
        # Clutter must be stripped
        assert "main.aux" not in namelist
        assert "main.log" not in namelist
        assert ".DS_Store" not in namelist
        assert "Thumbs.db" not in namelist

        # Backslashes normalized to forward slashes in tex file
        tex_content = zf.read("main.tex").decode("utf-8")
        assert "figs/chart.png" in tex_content
        assert "figs\\chart.png" not in tex_content


@pytest.mark.asyncio
async def test_write_to_file_tool(tmp_path):
    """Test write_to_file tool creating files and enforcing overwrite safety."""
    reg = ToolRegistry()
    target_file = tmp_path / "doc.md"

    res1 = await reg.execute("write_to_file", {
        "path": str(target_file),
        "content": "# Test Document\nHello",
        "overwrite": True
    })
    assert "Successfully wrote" in res1
    assert target_file.read_text(encoding="utf-8") == "# Test Document\nHello"

    # Test overwrite=False
    res_no_over = await reg.execute("write_to_file", {
        "path": str(target_file),
        "content": "New text",
        "overwrite": False
    })
    assert "FAILED" in res_no_over
    assert "already exists" in res_no_over


def test_new_skills_discovery_and_activation():
    """Verify that SkillsEngine indexes all 16 skills including overleaf and archive skills."""
    engine = get_skills_engine()
    skill_names = set(engine.skills.keys())
    assert "overleaf-latex-mastery" in skill_names
    assert "archive-data-orchestrator" in skill_names
    assert "proactive-task-planner" in skill_names
    assert "document-intelligence" in skill_names

    # Test activation
    res = engine.activate_skill("overleaf-latex-mastery")
    assert "Overleaf & LaTeX Publishing Mastery" in res
    assert "prepare_overleaf_archive" in res


@pytest.mark.asyncio
async def test_proactive_engine_overleaf_relevance():
    """Verify that RelevanceGate triggers proactive investigation on Overleaf and zip tasks."""
    gate = RelevanceGate()
    eval_res = await gate.evaluate(
        user_prompt="Can you edit this zip file on my disk and make it compatible to Overleaf?",
        main_response="I will inspect and format the archive for you."
    )
    assert eval_res["should_investigate"] is True
    assert "Overleaf" in eval_res["topic"]
    assert "latex_context" in eval_res["suggested_sources"]


@pytest.mark.asyncio
async def test_cli_slash_commands_latex_and_archive(tmp_path):
    """Test /latex and /archive CLI slash commands."""
    assistant = JarvisAssistant()

    # /archive without arg
    res_arch_help = await assistant.process("/archive")
    assert "Usage:" in res_arch_help

    # /latex on directory
    test_dir = tmp_path / "tex_dir"
    test_dir.mkdir()
    (test_dir / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\nHi\n\\end{document}\n", encoding="utf-8")
    res_latex = await assistant.process(f"/latex {test_dir}")
    assert "LaTeX & Overleaf Project Validation Report" in res_latex
