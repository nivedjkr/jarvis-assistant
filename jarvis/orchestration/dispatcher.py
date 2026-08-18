"""
AgentDispatcher for JARVIS Mk4
Coordinates request classification, goal planning, task assignment, and subtask execution loops.
Preserves direct tool execution path for simple requests.
"""

from typing import Dict, List, Any, Optional
from jarvis.agents import (
    BaseAgent, AgentResponse, ResearchAgent, CodingAgent, SystemAgent, CommunicationAgent
)
from jarvis.agents.planning_agent import PlanningAgent, GoalPlan
from jarvis.orchestration.task_tracker import TaskTracker, TaskStatus
from jarvis.orchestration.agentic_loop import AgenticLoop


class AgentDispatcher:
    """
    Main dispatcher routing user requests to direct execution or multi-agent planning & execution.
    """

    def __init__(self, max_iterations_per_agent: int = 5):
        self.planning_agent = PlanningAgent()
        self.agents: Dict[str, BaseAgent] = {
            "ResearchAgent": ResearchAgent(),
            "CodingAgent": CodingAgent(),
            "SystemAgent": SystemAgent(),
            "CommunicationAgent": CommunicationAgent(),
        }
        self.task_tracker = TaskTracker()
        self.agentic_loop = AgenticLoop(max_iterations=max_iterations_per_agent)

    async def dispatch(
        self,
        user_prompt: str,
        tool_registry,
        llm_client
    ) -> Dict[str, Any]:
        """
        Main entry point for request processing.
        Returns dict containing dispatch status, whether multi-step orchestration occurred,
        and response content.
        """
        plan: GoalPlan = await self.planning_agent.plan_goal(user_prompt, llm_client)

        # Simple request -> Direct Execution Bypass
        if not plan.is_multi_step or not plan.subtasks:
            return {
                "handled": False,  # Signal caller to use direct tool-calling loop
                "is_multi_step": False,
                "reasoning": plan.reasoning,
                "content": None
            }

        # Multi-step goal -> Execute subtasks via agentic loops
        parent_task = self.task_tracker.create_task(
            description=user_prompt,
            assigned_agent="PlanningAgent"
        )
        self.task_tracker.update_task(parent_task.task_id, status=TaskStatus.PLANNING)

        completed_results: List[str] = []

        for idx, subtask in enumerate(plan.subtasks, start=1):
            agent_name = subtask.assigned_agent
            agent = self.agents.get(agent_name, self.agents["ResearchAgent"])

            sub_prompt = f"Goal Context: {user_prompt}\nSubtask {idx}/{len(plan.subtasks)}: {subtask.description}"
            if completed_results:
                sub_prompt += f"\nPrevious Subtask Outputs:\n" + "\n".join(completed_results)

            res: AgentResponse = await self.agentic_loop.run(
                agent=agent,
                user_prompt=sub_prompt,
                tool_registry=tool_registry,
                llm_client=llm_client,
                task_tracker=self.task_tracker,
                parent_task_id=parent_task.task_id
            )

            if res.status == "WAITING_FOR_CONFIRMATION":
                self.task_tracker.update_task(
                    parent_task.task_id,
                    status=TaskStatus.WAITING_FOR_CONFIRMATION,
                    result=res.content
                )
                return {
                    "handled": True,
                    "is_multi_step": True,
                    "status": "WAITING_FOR_CONFIRMATION",
                    "content": res.content,
                    "tasks": self.task_tracker.list_all_tasks()
                }
            elif res.status == "FAILED":
                self.task_tracker.update_task(
                    parent_task.task_id,
                    status=TaskStatus.FAILED,
                    error=res.error
                )
                return {
                    "handled": True,
                    "is_multi_step": True,
                    "status": "FAILED",
                    "content": f"Task execution failed at step {idx}: {res.error}",
                    "tasks": self.task_tracker.list_all_tasks()
                }

            completed_results.append(f"[{agent_name}]: {res.content}")

        final_summary = "\n\n".join(completed_results)
        self.task_tracker.update_task(
            parent_task.task_id,
            status=TaskStatus.COMPLETED,
            result=final_summary
        )

        return {
            "handled": True,
            "is_multi_step": True,
            "status": "COMPLETED",
            "content": final_summary,
            "tasks": self.task_tracker.list_all_tasks()
        }
