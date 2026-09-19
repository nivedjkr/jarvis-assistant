"""
DAGPlanner — Mark 5.4 Adaptive Neuro-Symbolic Task Scheduler
Decomposes complex, multi-step goals into a Directed Acyclic Graph (DAG) of subtasks,
executes them with topological dependency resolution, monitors intermediate results,
and autonomously replans upon tool failure.
"""

import asyncio
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Set


@dataclass
class DAGTask:
    id: str
    title: str
    tool: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    status: str = "PENDING"  # PENDING | RUNNING | COMPLETED | FAILED | SKIPPED
    result: Optional[str] = None
    error: Optional[str] = None
    retries: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "tool": self.tool,
            "arguments": self.arguments,
            "depends_on": self.depends_on,
            "status": self.status,
            "result": (self.result[:300] + "...") if self.result and len(self.result) > 300 else self.result,
            "error": self.error,
            "retries": self.retries,
            "started_at": self.started_at,
            "completed_at": self.completed_at
        }


@dataclass
class DAGPlan:
    plan_id: str
    goal: str
    tasks: Dict[str, DAGTask] = field(default_factory=dict)
    status: str = "PENDING"  # PENDING | RUNNING | COMPLETED | FAILED | PARTIAL
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    execution_log: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "tasks": [t.to_dict() for t in self.tasks.values()],
            "log_count": len(self.execution_log)
        }


class DAGPlanner:
    """
    Autonomous Neuro-Symbolic Task Scheduler.
    Resolves dependency graphs, executes subtasks, and performs adaptive self-healing.
    """

    def __init__(self, llm_provider: Optional[Any] = None, max_retries_per_task: int = 2):
        self.llm_provider = llm_provider
        self.max_retries_per_task = max_retries_per_task

    def _get_provider(self):
        if self.llm_provider is None:
            try:
                from jarvis.llm_provider import NVIDIAProvider
                self.llm_provider = NVIDIAProvider()
            except Exception:
                pass
        return self.llm_provider

    async def create_plan(
        self,
        goal: str,
        available_tools: Optional[List[str]] = None,
        context: str = ""
    ) -> DAGPlan:
        """
        Decomposes a goal into an executable Directed Acyclic Graph (DAG).
        Uses LLM with fallback to robust heuristic planner if offline.
        """
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        tools = available_tools or [
            "inspect_project", "run_tests", "view_file", "replace_file_content",
            "search_hierarchical_memory", "web_search_live", "run_command"
        ]

        provider = self._get_provider()
        plan_tasks = None

        if provider and hasattr(provider, 'chat'):
            prompt = f"""You are JARVIS's Neuro-Symbolic Task Planner.
Decompose the following user goal into a structured Directed Acyclic Graph (DAG) of subtasks.
Goal: "{goal}"

Available tools: {json.dumps(tools[:25])}
Additional Context: {context or 'None'}

Return ONLY a JSON object with this exact structure:
{{
  "tasks": [
    {{
      "id": "task_1",
      "title": "Short descriptive title",
      "tool": "tool_name",
      "arguments": {{"key": "val"}},
      "depends_on": []
    }},
    {{
      "id": "task_2",
      "title": "Subsequent title",
      "tool": "tool_name",
      "arguments": {{"key": "val"}},
      "depends_on": ["task_1"]
    }}
  ]
}}
Ensure dependencies are strictly acyclic. No preamble or explanations."""

            try:
                res = await provider.chat(messages=[{"role": "user", "content": prompt}], max_tokens=1024)
                content = res.choices[0].message.content if hasattr(res, 'choices') and res.choices else str(res)
                
                # Extract JSON from code fences or raw string
                json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
                raw_json = json_match.group(1) if json_match else content.strip()
                parsed = json.loads(raw_json)
                if "tasks" in parsed and isinstance(parsed["tasks"], list) and parsed["tasks"]:
                    plan_tasks = {}
                    for item in parsed["tasks"]:
                        tid = str(item.get("id") or f"task_{len(plan_tasks)+1}")
                        plan_tasks[tid] = DAGTask(
                            id=tid,
                            title=item.get("title", f"Execute {item.get('tool')}"),
                            tool=item.get("tool", "run_command"),
                            arguments=item.get("arguments", {}),
                            depends_on=item.get("depends_on", [])
                        )
            except Exception as e:
                print(f"[DAG_PLANNER] LLM planning failed, using heuristic graph: {e}")

        # Fallback heuristic graph if LLM was unavailable or invalid
        if not plan_tasks:
            plan_tasks = self._create_heuristic_plan(goal)

        plan = DAGPlan(plan_id=plan_id, goal=goal, tasks=plan_tasks)
        self._validate_dag(plan)
        return plan

    def _create_heuristic_plan(self, goal: str) -> Dict[str, DAGTask]:
        """Creates an intelligent default DAG based on goal keywords."""
        tasks = {}
        goal_lower = goal.lower()
        goal_words = set(re.findall(r"\b[a-zA-Z0-9_-]+\b", goal_lower))
        if goal_words.intersection({"test", "tests", "testing", "fix", "debug", "code", "coding", "inspect", "repo", "repository"}):
            tasks["task_1"] = DAGTask(
                id="task_1",
                title="Inspect project architecture & entry points",
                tool="inspect_project",
                arguments={"path": "."},
                depends_on=[]
            )
            tasks["task_2"] = DAGTask(
                id="task_2",
                title="Query hierarchical memory for project history",
                tool="search_hierarchical_memory",
                arguments={"query": goal, "top_k": 3},
                depends_on=[]
            )
            tasks["task_3"] = DAGTask(
                id="task_3",
                title="Run test suite to verify baseline",
                tool="run_tests",
                arguments={"path": "."},
                depends_on=["task_1"]
            )
        else:
            tasks["task_1"] = DAGTask(
                id="task_1",
                title="Search contextual memory for relevant concepts",
                tool="search_hierarchical_memory",
                arguments={"query": goal, "top_k": 3},
                depends_on=[]
            )
            tasks["task_2"] = DAGTask(
                id="task_2",
                title="Execute live web search for external context",
                tool="web_search_live",
                arguments={"query": goal},
                depends_on=["task_1"]
            )

        return tasks

    def _validate_dag(self, plan: DAGPlan):
        """Ensures the DAG contains no circular dependencies."""
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def is_cyclic(t_id: str) -> bool:
            visited.add(t_id)
            rec_stack.add(t_id)
            task = plan.tasks.get(t_id)
            if task:
                for dep in task.depends_on:
                    if dep not in visited:
                        if is_cyclic(dep):
                            return True
                    elif dep in rec_stack:
                        return True
            rec_stack.remove(t_id)
            return False

        for task_id in list(plan.tasks.keys()):
            if task_id not in visited:
                if is_cyclic(task_id):
                    # Remove cyclic dependency to preserve DAG integrity
                    print(f"[DAG_PLANNER] Cyclic dependency detected involving {task_id}! Sanitizing.")
                    plan.tasks[task_id].depends_on = []

    async def execute_plan(
        self,
        plan: DAGPlan,
        tool_registry: Any,
        status_callback: Optional[Callable[[str, DAGTask], Any]] = None,
        max_steps: int = 15
    ) -> Dict[str, Any]:
        """
        Executes the DAG plan respecting topological dependencies.
        Autonomously performs self-healing replanning on failures.
        """
        plan.status = "RUNNING"
        step = 0

        while step < max_steps:
            step += 1
            # Find candidate tasks ready to run: status==PENDING and all depends_on are COMPLETED
            ready_tasks = []
            for task in plan.tasks.values():
                if task.status == "PENDING":
                    deps_satisfied = True
                    for dep_id in task.depends_on:
                        dep_task = plan.tasks.get(dep_id)
                        if not dep_task or dep_task.status != "COMPLETED":
                            deps_satisfied = False
                            break
                    if deps_satisfied:
                        ready_tasks.append(task)

            # If no tasks are ready, check if we're done or deadlocked
            if not ready_tasks:
                pending_count = sum(1 for t in plan.tasks.values() if t.status == "PENDING")
                running_count = sum(1 for t in plan.tasks.values() if t.status == "RUNNING")
                if pending_count == 0 and running_count == 0:
                    break  # All tasks finished
                # If there are still pending tasks but none can run due to failed dependencies:
                failed_deps = False
                for task in plan.tasks.values():
                    if task.status == "PENDING":
                        for dep_id in task.depends_on:
                            dep = plan.tasks.get(dep_id)
                            if dep and dep.status in {"FAILED", "SKIPPED"}:
                                task.status = "SKIPPED"
                                task.error = f"Predecessor '{dep_id}' {dep.status.lower()}"
                                failed_deps = True
                if not failed_deps:
                    break

            # Execute ready tasks
            for task in ready_tasks:
                task.status = "RUNNING"
                task.started_at = datetime.now().isoformat()
                if status_callback:
                    try:
                        res = status_callback("RUNNING", task)
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception:
                        pass

                # Execute tool
                try:
                    if hasattr(tool_registry, 'execute'):
                        out = await tool_registry.execute(task.tool, task.arguments)
                    else:
                        out = f"Tool '{task.tool}' executed with args {task.arguments}"
                    
                    # Detect execution errors in output
                    if isinstance(out, str) and ("FAILED:" in out or "ACCESS DENIED" in out or "Error:" in out):
                        task.status = "FAILED"
                        task.error = out
                    else:
                        task.status = "COMPLETED"
                        task.result = str(out)
                except Exception as e:
                    task.status = "FAILED"
                    task.error = str(e)

                task.completed_at = datetime.now().isoformat()
                plan.execution_log.append({
                    "step": step,
                    "task_id": task.id,
                    "tool": task.tool,
                    "status": task.status,
                    "timestamp": task.completed_at
                })

                # Self-healing replanning on failure
                if task.status == "FAILED" and task.retries < self.max_retries_per_task:
                    repaired = await self._replan_failed_task(plan, task, tool_registry)
                    if repaired:
                        task.retries += 1
                        task.status = "PENDING"
                        task.error = None

                if status_callback:
                    try:
                        res = status_callback(task.status, task)
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception:
                        pass

        # Calculate final plan status
        statuses = [t.status for t in plan.tasks.values()]
        if all(s == "COMPLETED" for s in statuses):
            plan.status = "COMPLETED"
        elif any(s == "COMPLETED" for s in statuses):
            plan.status = "PARTIAL"
        else:
            plan.status = "FAILED"

        plan.completed_at = datetime.now().isoformat()
        return plan.to_dict()

    async def _replan_failed_task(self, plan: DAGPlan, task: DAGTask, tool_registry: Any) -> bool:
        """
        Attempts self-healing repair on a failed task by adjusting arguments or fallback tool.
        """
        print(f"[DAG_PLANNER] Self-healing initiated for failed task '{task.id}' ({task.tool})")
        # Simple heuristic fallback rules:
        if task.tool == "inspect_project" and "path" in task.arguments:
            task.arguments["path"] = "."
            return True
        if task.tool == "web_search_live":
            # Fall back to web_search or query simplification
            query = task.arguments.get("query", "")
            task.arguments["query"] = " ".join(query.split()[:4])
            return True
        return False

    def render_ascii_dag(self, plan: DAGPlan) -> str:
        """Returns a clean ASCII visualization of the DAG plan."""
        status_icons = {
            "COMPLETED": "[bold green]✓[/]",
            "RUNNING": "[bold yellow]⏳[/]",
            "FAILED": "[bold red]✗[/]",
            "SKIPPED": "[dim]↷[/]",
            "PENDING": "[dim]○[/]"
        }
        lines = [
            f"◈ [bold cyan]DAG Execution Plan:[/] {plan.plan_id} ([bold]{plan.status}[/])",
            f"  Goal: [italic]{plan.goal}[/]",
            ""
        ]

        for t in plan.tasks.values():
            icon = status_icons.get(t.status, "○")
            deps_str = f" <- [dim]depends on: {', '.join(t.depends_on)}[/]" if t.depends_on else ""
            lines.append(f"  {icon} [bold]{t.id}[/]: {t.title} [cyan]({t.tool})[/]{deps_str}")
            if t.result and t.status == "COMPLETED":
                summary = t.result.strip().split("\n")[0][:80]
                lines.append(f"     [green]↳ Result:[/] {summary}...")
            elif t.error and t.status == "FAILED":
                lines.append(f"     [red]↳ Error:[/] {t.error[:80]}")

        return "\n".join(lines)
