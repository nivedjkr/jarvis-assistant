"""
AgenticLoop for JARVIS Mk4
Reusable execution loop that coordinates reasoning and tool calls for logical agents.
All tool executions go through the existing ToolRegistry and Security Gate.
"""

import json
import inspect
from typing import List, Dict, Any, Optional
from jarvis.agents.base_agent import BaseAgent, AgentResponse
from jarvis.orchestration.task_tracker import TaskTracker, TaskStatus


class AgenticLoop:
    """
    Executes a bounded reasoning-action loop for a specific agent.
    Strictly enforces max_iterations, respects RISKY_TOOLS pending confirmation flow,
    and returns structured AgentResponse.
    """

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations

    async def run(
        self,
        agent: BaseAgent,
        user_prompt: str,
        tool_registry,
        llm_client,
        task_tracker: Optional[TaskTracker] = None,
        parent_task_id: Optional[str] = None
    ) -> AgentResponse:
        task = None
        if task_tracker:
            task = task_tracker.create_task(
                description=user_prompt,
                assigned_agent=agent.name,
                parent_task_id=parent_task_id
            )
            task_tracker.update_task(task.task_id, status=TaskStatus.RUNNING)

        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": user_prompt}
        ]
        
        executed_tool_calls: List[Dict[str, Any]] = []
        iteration = 0
        final_content = ""

        while iteration < self.max_iterations:
            iteration += 1
            if task_tracker and task:
                task_tracker.update_task(
                    task.task_id,
                    current_step=f"Iteration {iteration}/{self.max_iterations}: reasoning",
                    increment_iteration=True
                )

            try:
                response = await agent.step(messages, tool_registry, llm_client)
            except Exception as e:
                err_msg = f"Agent reasoning error: {str(e)}"
                if task_tracker and task:
                    task_tracker.update_task(task.task_id, status=TaskStatus.FAILED, error=err_msg)
                return AgentResponse(
                    agent_name=agent.name,
                    content="",
                    status="FAILED",
                    error=err_msg
                )

            while inspect.isawaitable(response):
                response = await response

            if isinstance(response, str):
                final_content = response
                if task_tracker and task:
                    task_tracker.update_task(task.task_id, status=TaskStatus.COMPLETED, result=final_content)
                return AgentResponse(
                    agent_name=agent.name,
                    content=final_content,
                    status="COMPLETED",
                    tool_calls=executed_tool_calls
                )

            choices = getattr(response, 'choices', [])
            msg = choices[0].message if choices else None

            if not msg:
                final_content = str(response)
                if task_tracker and task:
                    task_tracker.update_task(task.task_id, status=TaskStatus.COMPLETED, result=final_content)
                return AgentResponse(
                    agent_name=agent.name,
                    content=final_content,
                    status="COMPLETED",
                    tool_calls=executed_tool_calls
                )

            if getattr(msg, 'tool_calls', None):
                # Model produced tool calls
                tool_calls_data = []
                for tc in msg.tool_calls:
                    tool_calls_data.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    })

                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": tool_calls_data
                })

                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except Exception:
                        args = {}

                    # Security & Permissions check: Ensure agent only calls allowed tools
                    if agent.allowed_tools is not None and fn_name not in agent.allowed_tools:
                        result = f"Error: Tool '{fn_name}' is not permitted for role '{agent.name}'."
                    else:
                        # Execute via existing ToolRegistry (which enforces RISKY_TOOLS confirmation gate)
                        try:
                            if hasattr(tool_registry, 'execute'):
                                result = await tool_registry.execute(fn_name, args)
                            else:
                                result = await tool_registry.execute_tool(fn_name, **args)
                        except Exception as te:
                            result = f"Tool Execution Error: {str(te)}"

                    str_result = str(result)
                    executed_tool_calls.append({"tool": fn_name, "args": args, "result": str_result})

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str_result
                    })

                    # Check for security confirmation gate trigger
                    if "PENDING_CONFIRMATION" in str_result or "CONFIRMATION REQUIRED" in str_result:
                        if task_tracker and task:
                            task_tracker.update_task(
                                task.task_id,
                                status=TaskStatus.WAITING_FOR_CONFIRMATION,
                                result=str_result
                            )
                        return AgentResponse(
                            agent_name=agent.name,
                            content=str_result,
                            status="WAITING_FOR_CONFIRMATION",
                            tool_calls=executed_tool_calls
                        )
            else:
                # Direct text response from agent
                final_content = msg.content or ""
                if task_tracker and task:
                    task_tracker.update_task(task.task_id, status=TaskStatus.COMPLETED, result=final_content)
                return AgentResponse(
                    agent_name=agent.name,
                    content=final_content,
                    status="COMPLETED",
                    tool_calls=executed_tool_calls
                )

        # Max iterations reached
        capped_msg = f"Task reached maximum iteration cap of {self.max_iterations} steps."
        if task_tracker and task:
            task_tracker.update_task(task.task_id, status=TaskStatus.COMPLETED, result=capped_msg)

        return AgentResponse(
            agent_name=agent.name,
            content=final_content or capped_msg,
            status="COMPLETED",
            tool_calls=executed_tool_calls
        )
