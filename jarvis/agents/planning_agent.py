"""
PlanningAgent for JARVIS Mk4
Evaluates user requests, classifies requests as SIMPLE or MULTI_STEP,
decomposes multi-step goals into subtasks, and assigns specialized agents.
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from jarvis.agents.base_agent import BaseAgent


@dataclass
class SubTaskPlan:
    description: str
    assigned_agent: str  # ResearchAgent, CodingAgent, SystemAgent, CommunicationAgent
    dependencies: List[int] = field(default_factory=list)


@dataclass
class GoalPlan:
    is_multi_step: bool
    reasoning: str
    subtasks: List[SubTaskPlan] = field(default_factory=list)


class PlanningAgent(BaseAgent):
    """Logical agent role for goal decomposition, plan synthesis, and delegation."""

    def __init__(self):
        system_prompt = (
            "You are the JARVIS Planning Agent.\n"
            "Your job is to analyze user requests and determine execution strategy:\n"
            "1. Determine if a request is SIMPLE (single direct tool call, time, status, basic question) or MULTI_STEP.\n"
            "2. If MULTI_STEP, break the goal into clear sequential subtasks.\n"
            "3. Assign each subtask to the most qualified specialized agent:\n"
            "   - ResearchAgent (search, memory, info retrieval)\n"
            "   - CodingAgent (reading/editing code, running tests, git, github)\n"
            "   - SystemAgent (system stats, launching apps, desktop/filesystem ops)\n"
            "   - CommunicationAgent (email, calendar, obsidian notes)\n"
            "Respond in valid JSON format."
        )
        super().__init__(
            name="PlanningAgent",
            role_description="High-level request classification, goal decomposition, and agent assignment.",
            system_prompt=system_prompt,
            allowed_tools=set()  # Planner does not directly call tools
        )

    def classify_request_rule_based(self, prompt: str) -> Optional[GoalPlan]:
        """
        Fast heuristic classification to bypass LLM latency for common simple queries.
        """
        p_lower = prompt.lower().strip()
        simple_triggers = [
            "what time", "current time", "what date", "today's date",
            "open chrome", "open notepad", "open calculator",
            "cpu usage", "system status", "memory status",
            "check email", "list emails", "unread emails",
            "check calendar", "list calendar"
        ]
        if any(trigger in p_lower for trigger in simple_triggers) and len(prompt.split()) <= 8:
            return GoalPlan(
                is_multi_step=False,
                reasoning="Rule-based classification identified simple direct query."
            )
        return None

    async def plan_goal(self, user_prompt: str, llm_client) -> GoalPlan:
        """
        Analyze prompt and produce GoalPlan. Uses rule-based fast path if applicable,
        else calls LLM reasoning.
        """
        fast_plan = self.classify_request_rule_based(user_prompt)
        if fast_plan:
            return fast_plan

        planning_prompt = (
            f"Analyze this user request: '{user_prompt}'\n\n"
            "Is this a SIMPLE single-step request or a MULTI_STEP request requiring planning/multiple agents?\n"
            "Return JSON with format:\n"
            "{\n"
            '  "is_multi_step": true/false,\n'
            '  "reasoning": "explanation",\n'
            '  "subtasks": [\n'
            '     {"description": "subtask details", "assigned_agent": "ResearchAgent|CodingAgent|SystemAgent|CommunicationAgent"}\n'
            "  ]\n"
            "}"
        )

        messages = [
            {"role": "system", "content": self.build_system_message()},
            {"role": "user", "content": planning_prompt}
        ]

        try:
            if hasattr(llm_client.provider, 'chat'):
                res = await llm_client.provider.chat(messages, tools=None, max_tokens=350)
            else:
                res = await llm_client.client.chat.completions.create(
                    model=llm_client.model,
                    messages=messages,
                    max_tokens=350,
                    stream=False
                )
            
            content = ""
            if isinstance(res, str):
                content = res
            elif getattr(res, 'choices', None):
                content = res.choices[0].message.content or ""

            # Attempt JSON parse
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            if start_idx != -1 and end_idx != -1:
                json_str = content[start_idx:end_idx+1]
                data = json.loads(json_str)
                is_multi = data.get("is_multi_step", False)
                reasoning = data.get("reasoning", "")
                raw_tasks = data.get("subtasks", [])

                subtasks = []
                for t in raw_tasks:
                    subtasks.append(SubTaskPlan(
                        description=t.get("description", ""),
                        assigned_agent=t.get("assigned_agent", "ResearchAgent")
                    ))
                return GoalPlan(is_multi_step=is_multi, reasoning=reasoning, subtasks=subtasks)

        except Exception as e:
            print(f"[PLANNER] Reasoning parse fallback: {e}")

        # Fallback to simple direct path on parse error
        return GoalPlan(
            is_multi_step=False,
            reasoning="Fallback to simple direct path."
        )
