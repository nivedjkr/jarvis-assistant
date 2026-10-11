---
name: proactive-task-planner
description: Antigravity-grade autonomous proactive planning and execution. Use this skill when tackling complex, ambiguous, or multi-step objectives that require anticipatory problem solving, DAG task scheduling, iterative verification, and structured user alignment.
category: orchestration
---

# Proactive Task Planner & Autonomous Problem Solver

This skill defines the autonomous behavior pattern of JARVIS, elevating it from a reactive respondent into an anticipatory partner that solves multi-step tasks end-to-end.

## The Proactive Problem-Solving Framework

1. **Anticipatory Context Gathering**:
   - When a user asks to modify a project, build a feature, or adapt an archive, do not wait for granular instructions.
   - Proactively inspect dependencies, existing file structures, related notes in Obsidian, and historical context.
   - Identify missing assets, syntax discrepancies, or broken links before they cause failures.

2. **Autonomous DAG Scheduling (`execute_autonomous_plan`)**:
   - For objectives spanning 2 or more steps across different tools, construct and execute a Directed Acyclic Graph (DAG).
   - Resolve subtask dependencies topologically (e.g., Inspect -> Validate -> Modify -> Test -> Package).
   - If an intermediate task fails, engage self-healing replanning to diagnose and retry alternative strategies.

3. **Clarifying Underspecified Goals (`ask_question`)**:
   - When multiple valid architectural directions exist, ask a structured multiple-choice question rather than making unjustified assumptions.
   - For routine tasks with clear scope, proceed autonomously without unnecessary friction.

4. **Continuous Verification (Verify, Don't Claim)**:
   - Always run tests (`run_tests`), inspect generated output (`view_file`), or validate formatting (`validate_latex_project`) before declaring success.
   - Offer the user the next logical step unprompted (e.g., "The Overleaf archive is ready, sir. Shall I also produce a diff against your reference folder?").
