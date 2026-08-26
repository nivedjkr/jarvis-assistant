"""
Mark 5 Proactive Follow-Up Engine for JARVIS.

Coordinates non-blocking background analysis, relevance gating, multi-source investigation,
value gating, rate limiting, and proactive follow-up delivery after the main response turn.
"""

import asyncio
import json
import time
import uuid
import re
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from jarvis.mission_manager import MissionManager, MissionDetector, MissionStatus


class TaskStatus(str, Enum):
    ANALYZING = "ANALYZING"
    INVESTIGATING = "INVESTIGATING"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class TaskOutcome(str, Enum):
    NO_ACTION = "NO_ACTION"
    FOLLOW_UP_SENT = "FOLLOW_UP_SENT"
    FAILED = "FAILED"


@dataclass
class ProactiveTask:
    task_id: str
    session_id: str
    user_prompt: str
    main_response: str
    topic: str = ""
    status: TaskStatus = TaskStatus.ANALYZING
    findings: List[Dict[str, Any]] = field(default_factory=list)
    final_outcome: TaskOutcome = TaskOutcome.NO_ACTION
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "user_prompt": self.user_prompt,
            "main_response": self.main_response,
            "topic": self.topic,
            "status": self.status.value if isinstance(self.status, TaskStatus) else str(self.status),
            "findings": self.findings,
            "final_outcome": self.final_outcome.value if isinstance(self.final_outcome, TaskOutcome) else str(self.final_outcome),
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }


class RelevanceGate:
    """
    Evaluates whether proactive background investigation is warranted for a user message.
    Filter out casual greetings, small talk, direct math, and simple routine queries.
    """

    EXCLUDED_PATTERNS = [
        r"^(hi|hello|hey|greetings|good morning|good evening|howdy)\b",
        r"^(thanks|thank you|ok|okay|cool|nice|got it|sure)\b",
        r"\b\d+\s*[\+\-\*/]\s*\d+\b",
        r"^what\s+(is|are)\s+\d+",
        r"^(what time|what date|what is the time)\b",
        r"^(open|close|launch)\s+\w+$",
    ]

    TRIGGER_KEYWORDS = [
        "work on", "working on", "building", "project", "architecture", "design",
        "plan", "planning", "implement", "developing", "learning", "exploring",
        "mark 5", "mark 4", "jarvis", "system", "feature", "framework", "database",
        "algorithm", "model", "migration", "integration"
    ]

    async def evaluate(
        self,
        user_prompt: str,
        main_response: str,
        llm_client: Optional[Any] = None
    ) -> Dict[str, Any]:
        prompt_clean = user_prompt.strip()
        lower_prompt = prompt_clean.lower()

        # Check exclusion patterns
        for pat in self.EXCLUDED_PATTERNS:
            if re.search(pat, lower_prompt):
                return {
                    "should_investigate": False,
                    "reason": "Excluded routine query or greeting pattern."
                }

        # Check length / minimal content
        words = lower_prompt.split()
        if len(words) < 3:
            return {
                "should_investigate": False,
                "reason": "Query too short for proactive investigation."
            }

        # Check trigger keywords or topics
        matched_triggers = [kw for kw in self.TRIGGER_KEYWORDS if kw in lower_prompt]
        if matched_triggers or len(words) >= 5:
            topic = " ".join(words[:6])
            if "mark 5" in lower_prompt or "mark v" in lower_prompt:
                topic = "Mark 5 architecture and features"
            elif matched_triggers:
                topic = f"{matched_triggers[0]} topic"

            return {
                "should_investigate": True,
                "reason": f"Detected actionable proactive topic (keywords: {matched_triggers or 'contextual query'}).",
                "topic": topic,
                "suggested_sources": ["web_search", "obsidian", "project_context"]
            }

        return {
            "should_investigate": False,
            "reason": "No actionable proactive topic detected."
        }


class ValueGate:
    """
    Evaluates findings collected during proactive investigation.
    Enforces strict quality, confidence, and non-redundancy criteria.
    """

    async def evaluate(
        self,
        user_prompt: str,
        main_response: str,
        findings: List[Dict[str, Any]]
    ) -> Optional[str]:
        if not findings:
            return None

        useful_insights = []
        lower_main = main_response.lower()

        for f in findings:
            content = str(f.get("content", "")).strip()
            if not content:
                continue

            # Check redundancy with main response
            lower_content = content.lower()
            if lower_content in lower_main:
                continue

            # Check minimal length & substance
            if len(content) >= 10 and "error" not in lower_content:
                useful_insights.append(content)

        if not useful_insights:
            return None

        # Format key insight
        insight = useful_insights[0]
        if len(insight) > 250:
            insight = insight[:247] + "..."

        return insight


class ProactiveFollowUpEngine:
    """
    Main engine orchestrating background proactive analysis, investigation, value gating,
    and event-driven follow-up delivery.
    """

    def __init__(self, cooldown_seconds: float = 30.0, db_path: str = "jarvis/data/jarvis.db"):
        self.relevance_gate = RelevanceGate()
        self.value_gate = ValueGate()
        self.mission_detector = MissionDetector()
        self.mission_manager = MissionManager(db_path=db_path)
        self.cooldown_seconds = cooldown_seconds
        self.active_tasks: Dict[str, ProactiveTask] = {}
        self.running_async_tasks: Dict[str, asyncio.Task] = {}
        self.last_followup_time: Dict[str, float] = {}


    def is_session_in_cooldown(self, session_id: str) -> bool:
        last = self.last_followup_time.get(session_id, 0.0)
        return (time.time() - last) < self.cooldown_seconds

    def cancel_session_tasks(self, session_id: str):
        """Cancel any running proactive task for the given session."""
        for tid, task in list(self.active_tasks.items()):
            if task.session_id == session_id and task.status in (TaskStatus.ANALYZING, TaskStatus.INVESTIGATING, TaskStatus.EVALUATING):
                task.status = TaskStatus.CANCELLED
                task.completed_at = time.time()
                if tid in self.running_async_tasks:
                    self.running_async_tasks[tid].cancel()

    async def analyze_and_followup(
        self,
        session_id: str,
        user_prompt: str,
        main_response: str,
        tool_registry: Any,
        llm_client: Any,
        event_callback: Optional[Callable[[Dict[str, Any]], Any]] = None
    ) -> ProactiveTask:
        # Enforce single active task per session
        self.cancel_session_tasks(session_id)

        task_id = f"proactive_{uuid.uuid4().hex[:8]}"
        task = ProactiveTask(
            task_id=task_id,
            session_id=session_id,
            user_prompt=user_prompt,
            main_response=main_response,
            status=TaskStatus.ANALYZING
        )
        self.active_tasks[task_id] = task

        async def _emit_event(payload: Dict[str, Any]):
            if event_callback:
                try:
                    res = event_callback(payload)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as ee:
                    print(f"[PROACTIVE] Event callback error: {ee}")

        async def _run_pipeline():
            try:
                # 1. Emit Analysis Started
                await _emit_event({
                    "type": "proactive_event",
                    "event": "proactive_analysis_started",
                    "task_id": task_id,
                    "session_id": session_id
                })

                # Check for Mission Proposal candidate
                m_eval = await self.mission_detector.evaluate(user_prompt, main_response)
                if m_eval.get("should_propose_mission"):
                    proposed_mission = self.mission_manager.propose_mission(
                        title=m_eval["title"],
                        objective=m_eval["objective"],
                        description=m_eval.get("reason", ""),
                        source_conversation_id=session_id
                    )

                    await _emit_event({
                        "type": "mission_event",
                        "event": "mission_proposed",
                        "mission": proposed_mission.to_dict(),
                        "session_id": session_id
                    })

                    followup_text = (
                        f"That sounds like an ongoing objective, sir. "
                        f"Shall I create an active mission for it? "
                        f"(Mission: '{proposed_mission.title}' [ID: {proposed_mission.id}])"
                    )

                    task.status = TaskStatus.COMPLETED
                    task.final_outcome = TaskOutcome.FOLLOW_UP_SENT
                    task.completed_at = time.time()
                    self.last_followup_time[session_id] = time.time()

                    await _emit_event({
                        "type": "proactive_followup",
                        "event": "proactive_followup_sent",
                        "task_id": task_id,
                        "session_id": session_id,
                        "text": followup_text,
                        "mission_id": proposed_mission.id
                    })
                    return task

                # Check Cooldown
                if self.is_session_in_cooldown(session_id):

                    task.status = TaskStatus.COMPLETED
                    task.final_outcome = TaskOutcome.NO_ACTION
                    task.completed_at = time.time()
                    await _emit_event({
                        "type": "proactive_event",
                        "event": "proactive_no_action",
                        "task_id": task_id,
                        "reason": "Session in proactive cooldown period."
                    })
                    return task

                # 2. Relevance Gate
                rel_eval = await self.relevance_gate.evaluate(user_prompt, main_response, llm_client)
                if not rel_eval.get("should_investigate"):
                    task.status = TaskStatus.COMPLETED
                    task.final_outcome = TaskOutcome.NO_ACTION
                    task.completed_at = time.time()
                    await _emit_event({
                        "type": "proactive_event",
                        "event": "proactive_no_action",
                        "task_id": task_id,
                        "reason": rel_eval.get("reason", "Not relevant.")
                    })
                    return task

                topic = rel_eval.get("topic", user_prompt)
                task.topic = topic
                task.status = TaskStatus.INVESTIGATING

                # 3. Emit Investigation Started
                await _emit_event({
                    "type": "proactive_event",
                    "event": "proactive_investigation_started",
                    "task_id": task_id,
                    "topic": topic
                })

                # 4. Execute Investigation Tools
                sources = rel_eval.get("suggested_sources", ["web_search"])
                findings = []

                for src in sources:
                    try:
                        if src == "web_search" and hasattr(tool_registry, "execute"):
                            # Perform web search query
                            search_res = await asyncio.wait_for(
                                tool_registry.execute("web_search_live", {"query": topic}),
                                timeout=15.0
                            )
                            if search_res and "Error" not in str(search_res):
                                findings.append({"source": "web_search", "content": str(search_res)})
                        elif src == "obsidian" and hasattr(tool_registry, "execute"):
                            obs_res = await asyncio.wait_for(
                                tool_registry.execute("search_obsidian", {"query": topic}),
                                timeout=15.0
                            )
                            if obs_res and "no matching" not in str(obs_res).lower() and "Error" not in str(obs_res):
                                findings.append({"source": "obsidian", "content": str(obs_res)})
                        elif src == "project_context" and hasattr(tool_registry, "execute"):
                            proj_res = await asyncio.wait_for(
                                tool_registry.execute("inspect_project", {"path": "."}),
                                timeout=15.0
                            )
                            if proj_res and "Error" not in str(proj_res):
                                findings.append({"source": "project_context", "content": str(proj_res)[:300]})
                    except Exception as ie:
                        print(f"[PROACTIVE] Investigation source '{src}' error: {ie}")

                    await _emit_event({
                        "type": "proactive_event",
                        "event": "proactive_source_complete",
                        "task_id": task_id,
                        "source": src
                    })

                task.findings = findings
                task.status = TaskStatus.EVALUATING

                await _emit_event({
                    "type": "proactive_event",
                    "event": "proactive_result_ready",
                    "task_id": task_id
                })

                # 5. Value Gate Evaluation
                insight = await self.value_gate.evaluate(user_prompt, main_response, findings)
                if not insight:
                    task.status = TaskStatus.COMPLETED
                    task.final_outcome = TaskOutcome.NO_ACTION
                    task.completed_at = time.time()
                    await _emit_event({
                        "type": "proactive_event",
                        "event": "proactive_no_action",
                        "task_id": task_id,
                        "reason": "No high-value non-redundant findings."
                    })
                    return task

                # 6. Format & Deliver Proactive Follow-Up Message
                followup_text = (
                    f"One more thing, sir. I investigated {topic} while we were talking, "
                    f"and found a relevant approach: {insight}"
                )

                task.status = TaskStatus.COMPLETED
                task.final_outcome = TaskOutcome.FOLLOW_UP_SENT
                task.completed_at = time.time()
                self.last_followup_time[session_id] = time.time()

                await _emit_event({
                    "type": "proactive_followup",
                    "event": "proactive_followup_sent",
                    "task_id": task_id,
                    "session_id": session_id,
                    "text": followup_text
                })

                return task

            except asyncio.CancelledError:
                task.status = TaskStatus.CANCELLED
                task.final_outcome = TaskOutcome.FAILED
                task.completed_at = time.time()
                raise
            except Exception as e:
                print(f"[PROACTIVE ERROR] Task '{task_id}' failed: {e}")
                task.status = TaskStatus.FAILED
                task.final_outcome = TaskOutcome.FAILED
                task.completed_at = time.time()
                await _emit_event({
                    "type": "proactive_event",
                    "event": "proactive_no_action",
                    "task_id": task_id,
                    "reason": f"Proactive investigation encountered error: {e}"
                })
                return task
            finally:
                self.running_async_tasks.pop(task_id, None)

        async_task = asyncio.create_task(_run_pipeline())
        self.running_async_tasks[task_id] = async_task
        return task
