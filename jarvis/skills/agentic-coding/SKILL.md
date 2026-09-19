---
name: agentic-coding
description: Antigravity's verified debug-loop engineering skill. Use this skill when inspecting unfamiliar projects, fixing bugs, running test suites, and performing surgical code modifications with verify-not-claim rigor.
category: coding
---

# Agentic Coding & Verified Debug Loop

The verified debug-loop pattern is the gold standard for agentic software engineering. You must never claim a fix or feature is complete without running tests to verify it.

## 5-Step Debug Loop Discipline

1. **Inspect Before Modifying**:
   - Always call `inspect_project` or `view_file` to observe directory structure, entry points, dependencies, and test setup.
   - Never guess file layouts or imports.
2. **Run Baseline Tests**:
   - Always call `run_tests` BEFORE making code edits to establish exact baseline test results (passed, failed, skipped) and capture stack traces.
3. **Surgical Modifications**:
   - Use `replace_file_content` for precise chunk search-and-replace rather than rewriting entire files.
   - For creating new files, use `write_file`.
   - Preserve all existing comments, docstrings, and non-target logic.
4. **Re-run Tests to Verify**:
   - Call `run_tests` immediately after applying code edits.
   - Check if the failure count dropped and whether new regressions appeared.
5. **Execution Cap & Safety**:
   - Cap iterative debugging at 5 turns. If still failing, analyze root causes or ask clarifying questions.
   - Respect sandbox boundaries (`ALLOWED_ROOTS`) and security policies at all times.
