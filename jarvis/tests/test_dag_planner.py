import pytest
from jarvis.orchestration.dag_planner import DAGTask, DAGPlan, DAGPlanner
from jarvis.tools import ToolRegistry, validate_tool_schemas


def test_dag_planner_data_structures():
    """Verify DAGTask and DAGPlan serialization and lifecycle states."""
    task = DAGTask(
        id="task_1",
        title="Check system vitals",
        tool="get_system_status",
        arguments={},
        depends_on=[]
    )
    assert task.status == "PENDING"
    d = task.to_dict()
    assert d["id"] == "task_1"
    assert d["tool"] == "get_system_status"

    plan = DAGPlan(plan_id="plan_test_01", goal="Verify system health", tasks={"task_1": task})
    assert plan.status == "PENDING"
    assert len(plan.tasks) == 1
    plan_dict = plan.to_dict()
    assert plan_dict["goal"] == "Verify system health"


@pytest.mark.asyncio
async def test_dag_planner_heuristic_generation():
    """Test heuristic DAG generation for coding and general goals."""
    planner = DAGPlanner()
    
    # Heuristic coding plan
    code_heuristic = planner._create_heuristic_plan("inspect repo and fix failing tests")
    assert len(code_heuristic) >= 2
    assert "task_1" in code_heuristic
    assert "task_2" in code_heuristic
    assert "task_1" in code_heuristic["task_3"].depends_on

    # Heuristic general plan
    gen_heuristic = planner._create_heuristic_plan("research the latest release notes for Python 3.12")
    assert len(gen_heuristic) >= 2
    assert "task_2" in gen_heuristic
    assert "task_1" in gen_heuristic["task_2"].depends_on

    # Live plan via create_plan
    gen_plan = await planner.create_plan("research the latest release notes for Python 3.12")
    assert len(gen_plan.tasks) >= 1
    for t in gen_plan.tasks.values():
        assert isinstance(t.depends_on, list)


@pytest.mark.asyncio
async def test_dag_plan_execution_and_dependency_resolution():
    """Test DAG execution resolving dependencies in topological order."""
    planner = DAGPlanner()
    registry = ToolRegistry()

    # Create synthetic 2-stage plan
    plan = DAGPlan(
        plan_id="plan_exec_test",
        goal="Check status and search memory",
        tasks={
            "task_1": DAGTask(
                id="task_1",
                title="Get system status",
                tool="get_system_status",
                arguments={},
                depends_on=[]
            ),
            "task_2": DAGTask(
                id="task_2",
                title="Search memory for architecture",
                tool="search_hierarchical_memory",
                arguments={"query": "architecture"},
                depends_on=["task_1"]  # Must run after task_1
            )
        }
    )

    res = await planner.execute_plan(plan, tool_registry=registry)
    assert res["status"] in {"COMPLETED", "PARTIAL"}
    assert plan.tasks["task_1"].status == "COMPLETED"
    assert plan.tasks["task_2"].status == "COMPLETED"
    assert plan.tasks["task_1"].started_at is not None
    assert plan.tasks["task_2"].started_at is not None


def test_dag_ascii_rendering():
    """Verify ASCII diagram rendering."""
    planner = DAGPlanner()
    plan = DAGPlan(
        plan_id="plan_render_01",
        goal="Run tests and report results",
        tasks={
            "task_1": DAGTask(id="task_1", title="Step 1", tool="inspect_project", status="COMPLETED", result="Project OK"),
            "task_2": DAGTask(id="task_2", title="Step 2", tool="run_tests", depends_on=["task_1"], status="PENDING")
        }
    )
    ascii_out = planner.render_ascii_dag(plan)
    assert "plan_render_01" in ascii_out
    assert "DAG Execution Plan" in ascii_out
    assert "Step 1" in ascii_out
    assert "Step 2" in ascii_out
    assert "depends on: task_1" in ascii_out


@pytest.mark.asyncio
async def test_autonomous_plan_tool_registered():
    """Verify execute_autonomous_plan is in ToolRegistry and schemas validate."""
    registry = ToolRegistry()
    assert validate_tool_schemas(registry) is True
    assert "execute_autonomous_plan" in registry.tools
