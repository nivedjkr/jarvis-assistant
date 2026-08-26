"""
Persistent Mission Intelligence System for JARVIS Mark 5.

Provides canonical Mission and MissionTask data models, SQLite persistent storage,
controlled state transitions, mission detection, approval workflow, and planning.
"""

import sqlite3
import json
import time
import uuid
import re
import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Set
from pathlib import Path


class MissionStatus(str, Enum):
    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    WAITING = "WAITING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MissionTaskStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


ALLOWED_MISSION_TRANSITIONS: Dict[MissionStatus, Set[MissionStatus]] = {
    MissionStatus.PROPOSED: {MissionStatus.ACTIVE, MissionStatus.CANCELLED},
    MissionStatus.ACTIVE: {MissionStatus.PLANNING, MissionStatus.EXECUTING, MissionStatus.WAITING, MissionStatus.PAUSED, MissionStatus.COMPLETED, MissionStatus.FAILED, MissionStatus.CANCELLED},
    MissionStatus.PLANNING: {MissionStatus.EXECUTING, MissionStatus.WAITING, MissionStatus.PAUSED, MissionStatus.COMPLETED, MissionStatus.FAILED, MissionStatus.CANCELLED},
    MissionStatus.EXECUTING: {MissionStatus.WAITING, MissionStatus.PAUSED, MissionStatus.COMPLETED, MissionStatus.FAILED, MissionStatus.CANCELLED},
    MissionStatus.WAITING: {MissionStatus.EXECUTING, MissionStatus.ACTIVE, MissionStatus.PAUSED, MissionStatus.COMPLETED, MissionStatus.FAILED, MissionStatus.CANCELLED},
    MissionStatus.PAUSED: {MissionStatus.ACTIVE, MissionStatus.EXECUTING, MissionStatus.CANCELLED},
    MissionStatus.COMPLETED: {MissionStatus.ACTIVE},
    MissionStatus.FAILED: {MissionStatus.ACTIVE},
    MissionStatus.CANCELLED: {MissionStatus.ACTIVE},
}

ALLOWED_TASK_TRANSITIONS: Dict[MissionTaskStatus, Set[MissionTaskStatus]] = {
    MissionTaskStatus.PENDING: {MissionTaskStatus.READY, MissionTaskStatus.RUNNING, MissionTaskStatus.CANCELLED},
    MissionTaskStatus.READY: {MissionTaskStatus.RUNNING, MissionTaskStatus.WAITING, MissionTaskStatus.CANCELLED},
    MissionTaskStatus.RUNNING: {MissionTaskStatus.WAITING, MissionTaskStatus.COMPLETED, MissionTaskStatus.FAILED, MissionTaskStatus.CANCELLED},
    MissionTaskStatus.WAITING: {MissionTaskStatus.READY, MissionTaskStatus.RUNNING, MissionTaskStatus.COMPLETED, MissionTaskStatus.FAILED, MissionTaskStatus.CANCELLED},
    MissionTaskStatus.COMPLETED: {MissionTaskStatus.PENDING, MissionTaskStatus.READY},
    MissionTaskStatus.FAILED: {MissionTaskStatus.PENDING, MissionTaskStatus.READY},
    MissionTaskStatus.CANCELLED: {MissionTaskStatus.PENDING, MissionTaskStatus.READY},
}


def validate_mission_transition(current: MissionStatus, target: MissionStatus):
    if current == target:
        return
    allowed = ALLOWED_MISSION_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(f"Invalid Mission state transition from '{current.value}' to '{target.value}'. Allowed: {[s.value for s in allowed]}")


def validate_task_transition(current: MissionTaskStatus, target: MissionTaskStatus):
    if current == target:
        return
    allowed = ALLOWED_TASK_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(f"Invalid Task state transition from '{current.value}' to '{target.value}'. Allowed: {[s.value for s in allowed]}")


@dataclass
class MissionTask:
    id: str
    mission_id: str
    title: str
    description: str = ""
    status: MissionTaskStatus = MissionTaskStatus.PENDING
    priority: str = "MEDIUM"
    depends_on: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    result: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "mission_id": self.mission_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value if isinstance(self.status, MissionTaskStatus) else str(self.status),
            "priority": self.priority,
            "depends_on": self.depends_on,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error
        }


@dataclass
class Mission:
    id: str
    title: str
    objective: str
    description: str = ""
    status: MissionStatus = MissionStatus.PROPOSED
    priority: str = "MEDIUM"
    source_conversation_id: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    last_activity_at: float = field(default_factory=time.time)
    next_review_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    tasks: List[MissionTask] = field(default_factory=list)

    @property
    def task_count(self) -> int:
        return len(self.tasks)

    @property
    def completed_task_count(self) -> int:
        return sum(1 for t in self.tasks if t.status == MissionTaskStatus.COMPLETED)

    @property
    def progress_percentage(self) -> float:
        if not self.tasks:
            return 0.0
        return round((self.completed_task_count / self.task_count) * 100.0, 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "objective": self.objective,
            "description": self.description,
            "status": self.status.value if isinstance(self.status, MissionStatus) else str(self.status),
            "priority": self.priority,
            "source_conversation_id": self.source_conversation_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_activity_at": self.last_activity_at,
            "next_review_at": self.next_review_at,
            "metadata": self.metadata,
            "progress_percentage": self.progress_percentage,
            "task_count": len(self.tasks),
            "completed_task_count": sum(1 for t in self.tasks if t.status == MissionTaskStatus.COMPLETED),
            "tasks": [t.to_dict() for t in self.tasks]
        }


class MissionManager:
    """
    Manages SQLite database storage for missions and tasks, controlled transitions,
    and task lifecycles.
    """

    def __init__(self, db_path: str = "jarvis/data/jarvis.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS missions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL,
                    priority TEXT DEFAULT 'MEDIUM',
                    source_conversation_id TEXT,
                    created_at REAL,
                    updated_at REAL,
                    last_activity_at REAL,
                    next_review_at REAL,
                    metadata TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mission_tasks (
                    id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL,
                    priority TEXT DEFAULT 'MEDIUM',
                    depends_on TEXT,
                    created_at REAL,
                    updated_at REAL,
                    completed_at REAL,
                    result TEXT,
                    error TEXT,
                    FOREIGN KEY(mission_id) REFERENCES missions(id) ON DELETE CASCADE
                )
            """)
            conn.commit()

    def propose_mission(
        self,
        title: str,
        objective: str,
        description: str = "",
        source_conversation_id: str = "",
        priority: str = "MEDIUM",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Mission:
        mission_id = f"mission_{uuid.uuid4().hex[:8]}"
        now = time.time()
        meta_json = json.dumps(metadata or {})

        mission = Mission(
            id=mission_id,
            title=title,
            objective=objective,
            description=description,
            status=MissionStatus.PROPOSED,
            priority=priority,
            source_conversation_id=source_conversation_id,
            created_at=now,
            updated_at=now,
            last_activity_at=now,
            metadata=metadata or {}
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO missions (
                    id, title, objective, description, status, priority,
                    source_conversation_id, created_at, updated_at, last_activity_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                mission.id, mission.title, mission.objective, mission.description,
                mission.status.value, mission.priority, mission.source_conversation_id,
                mission.created_at, mission.updated_at, mission.last_activity_at, meta_json
            ))
            conn.commit()

        return mission

    def approve_mission(self, mission_id: str) -> Mission:
        mission = self.get_mission(mission_id)
        if not mission:
            raise KeyError(f"Mission '{mission_id}' not found.")

        validate_mission_transition(mission.status, MissionStatus.ACTIVE)
        self.update_mission_status(mission_id, MissionStatus.ACTIVE)
        
        # Generate initial planning tasks
        self.update_mission_status(mission_id, MissionStatus.PLANNING)
        self.generate_initial_plan(mission_id)
        self.update_mission_status(mission_id, MissionStatus.EXECUTING)

        return self.get_mission(mission_id)

    def update_mission_status(self, mission_id: str, new_status: MissionStatus) -> Mission:
        mission = self.get_mission(mission_id)
        if not mission:
            raise KeyError(f"Mission '{mission_id}' not found.")

        validate_mission_transition(mission.status, new_status)
        now = time.time()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE missions
                SET status = ?, updated_at = ?, last_activity_at = ?
                WHERE id = ?
            """, (new_status.value, now, now, mission_id))
            conn.commit()

        return self.get_mission(mission_id)

    def pause_mission(self, mission_id: str) -> Mission:
        return self.update_mission_status(mission_id, MissionStatus.PAUSED)

    def resume_mission(self, mission_id: str) -> Mission:
        return self.update_mission_status(mission_id, MissionStatus.ACTIVE)

    def cancel_mission(self, mission_id: str) -> Mission:
        return self.update_mission_status(mission_id, MissionStatus.CANCELLED)

    def create_task(
        self,
        mission_id: str,
        title: str,
        description: str = "",
        priority: str = "MEDIUM",
        depends_on: Optional[List[str]] = None
    ) -> MissionTask:
        mission = self.get_mission(mission_id)
        if not mission:
            raise KeyError(f"Mission '{mission_id}' not found.")

        task_id = f"mtask_{uuid.uuid4().hex[:8]}"
        now = time.time()
        deps_json = json.dumps(depends_on or [])

        task = MissionTask(
            id=task_id,
            mission_id=mission_id,
            title=title,
            description=description,
            status=MissionTaskStatus.PENDING,
            priority=priority,
            depends_on=depends_on or [],
            created_at=now,
            updated_at=now
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO mission_tasks (
                    id, mission_id, title, description, status, priority,
                    depends_on, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.id, task.mission_id, task.title, task.description,
                task.status.value, task.priority, deps_json, task.created_at, task.updated_at
            ))
            cursor.execute("""
                UPDATE missions SET updated_at = ?, last_activity_at = ? WHERE id = ?
            """, (now, now, mission_id))
            conn.commit()

        return task

    def update_task_status(
        self,
        task_id: str,
        new_status: MissionTaskStatus,
        result: Optional[str] = None,
        error: Optional[str] = None
    ) -> MissionTask:
        task = self.get_task(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found.")

        validate_task_transition(task.status, new_status)
        now = time.time()
        completed_at = now if new_status in (MissionTaskStatus.COMPLETED, MissionTaskStatus.FAILED, MissionTaskStatus.CANCELLED) else task.completed_at

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE mission_tasks
                SET status = ?, updated_at = ?, completed_at = ?, result = ?, error = ?
                WHERE id = ?
            """, (new_status.value, now, completed_at, result or task.result, error or task.error, task_id))

            cursor.execute("""
                UPDATE missions SET updated_at = ?, last_activity_at = ? WHERE id = ?
            """, (now, now, task.mission_id))
            conn.commit()

        # Check mission completion status
        mission = self.get_mission(task.mission_id)
        if mission and mission.tasks:
            all_completed = all(t.status == MissionTaskStatus.COMPLETED for t in mission.tasks)
            any_failed = any(t.status == MissionTaskStatus.FAILED for t in mission.tasks)

            if all_completed and mission.status not in (MissionStatus.COMPLETED, MissionStatus.CANCELLED):
                self.update_mission_status(mission.id, MissionStatus.COMPLETED)
            elif any_failed and mission.status not in (MissionStatus.FAILED, MissionStatus.CANCELLED):
                self.update_mission_status(mission.id, MissionStatus.FAILED)

        return self.get_task(task_id)

    def generate_initial_plan(self, mission_id: str) -> List[MissionTask]:
        mission = self.get_mission(mission_id)
        if not mission:
            return []

        title_lower = mission.title.lower()
        obj_lower = mission.objective.lower()

        created_tasks = []
        if "internship" in title_lower or "internship" in obj_lower:
            t1 = self.create_task(mission_id, "Research target companies & software engineering roles", "Identify 10-15 target companies and application deadlines.")
            t2 = self.create_task(mission_id, "Update resume & GitHub portfolio", "Refine project descriptions, resume PDF, and pinned GitHub repos.", depends_on=[t1.id])
            t3 = self.create_task(mission_id, "Track applications and outreach", "Submit applications and maintain application tracker.", depends_on=[t2.id])
            created_tasks.extend([t1, t2, t3])
        else:
            t1 = self.create_task(mission_id, f"Research requirements for {mission.title}", f"Analyze goal scope: {mission.objective}")
            t2 = self.create_task(mission_id, "Execute initial subtask milestones", "Carry out primary action items.", depends_on=[t1.id])
            t3 = self.create_task(mission_id, "Verify results and complete objective", "Ensure objective deliverables are met.", depends_on=[t2.id])
            created_tasks.extend([t1, t2, t3])

        return created_tasks

    def get_mission(self, mission_id: str) -> Optional[Mission]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM missions WHERE id = ?", (mission_id,))
            row = cursor.fetchone()
            if not row:
                return None

            metadata = json.loads(row["metadata"]) if row["metadata"] else {}
            
            # Fetch tasks
            cursor.execute("SELECT * FROM mission_tasks WHERE mission_id = ? ORDER BY created_at ASC", (mission_id,))
            task_rows = cursor.fetchall()
            tasks = []
            for tr in task_rows:
                deps = json.loads(tr["depends_on"]) if tr["depends_on"] else []
                tasks.append(MissionTask(
                    id=tr["id"],
                    mission_id=tr["mission_id"],
                    title=tr["title"],
                    description=tr["description"] or "",
                    status=MissionTaskStatus(tr["status"]),
                    priority=tr["priority"] or "MEDIUM",
                    depends_on=deps,
                    created_at=tr["created_at"],
                    updated_at=tr["updated_at"],
                    completed_at=tr["completed_at"],
                    result=tr["result"],
                    error=tr["error"]
                ))

            return Mission(
                id=row["id"],
                title=row["title"],
                objective=row["objective"],
                description=row["description"] or "",
                status=MissionStatus(row["status"]),
                priority=row["priority"] or "MEDIUM",
                source_conversation_id=row["source_conversation_id"] or "",
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                last_activity_at=row["last_activity_at"],
                next_review_at=row["next_review_at"],
                metadata=metadata,
                tasks=tasks
            )

    def get_task(self, task_id: str) -> Optional[MissionTask]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM mission_tasks WHERE id = ?", (task_id,))
            tr = cursor.fetchone()
            if not tr:
                return None

            deps = json.loads(tr["depends_on"]) if tr["depends_on"] else []
            return MissionTask(
                id=tr["id"],
                mission_id=tr["mission_id"],
                title=tr["title"],
                description=tr["description"] or "",
                status=MissionTaskStatus(tr["status"]),
                priority=tr["priority"] or "MEDIUM",
                depends_on=deps,
                created_at=tr["created_at"],
                updated_at=tr["updated_at"],
                completed_at=tr["completed_at"],
                result=tr["result"],
                error=tr["error"]
            )

    def list_missions(self, status: Optional[MissionStatus] = None, limit: int = 50) -> List[Mission]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT id FROM missions WHERE status = ? ORDER BY updated_at DESC LIMIT ?", (status.value, limit))
            else:
                cursor.execute("SELECT id FROM missions ORDER BY updated_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()

        return [self.get_mission(r["id"]) for r in rows if self.get_mission(r["id"]) is not None]


class MissionDetector:
    """
    Evaluates user prompt messages for meaningful ongoing objectives.
    Excludes routine calculations, greetings, small talk, and temporary errands.
    """

    EXCLUDED_PATTERNS = [
        r"^(hi|hello|hey|greetings|good morning|good evening|howdy)\b",
        r"^(thanks|thank you|ok|okay|cool|nice|got it|sure)\b",
        r"\b\d+\s*[\+\-\*/]\s*\d+\b",
        r"^what\s+(is|are)\s+",
        r"^(what time|what date|what is the time)\b",
        r"^(open|close|launch)\s+\w+$",
        r"^(remind me|set timer|alarm)\b",
    ]

    GOAL_PATTERNS = [
        (r"\b(want to|going to|plan to|aiming to|need to|looking to)\s+(find|get|land|secure|search for)\s+a\s+(\w+\s+)?internship\b", "Find a suitable internship", "Find and secure a suitable internship position."),
        (r"\b(want to|going to|plan to|aiming to)\s+(build|develop|create|launch|start)\s+a\s+(new\s+)?(\w+\s+)?(app|project|startup|system|website|server)\b", "Build and launch project", "Build, test, and deploy project deliverables."),
        (r"\b(want to|going to|plan to|aiming to)\s+(learn|master|study)\s+(\w+)\b", "Master new skill/topic", "Study and achieve technical proficiency in target topic."),
    ]

    async def evaluate(self, user_prompt: str, main_response: str = "") -> Dict[str, Any]:
        prompt_clean = user_prompt.strip()
        lower_prompt = prompt_clean.lower()

        # Check exclusion rules
        for pat in self.EXCLUDED_PATTERNS:
            if re.search(pat, lower_prompt):
                return {"should_propose_mission": False, "reason": "Excluded routine or errand pattern."}

        # Check explicit goal patterns
        for pat, default_title, default_obj in self.GOAL_PATTERNS:
            match = re.search(pat, lower_prompt)
            if match:
                matched_text = match.group(0)
                title = default_title
                if "internship" in lower_prompt:
                    title = "Find and secure a suitable internship"
                return {
                    "should_propose_mission": True,
                    "title": title,
                    "objective": default_obj,
                    "reason": f"Detected long-term goal statement: '{matched_text}'",
                    "confidence": 0.9
                }

        # General heuristic for long-term goal statements
        goal_keywords = ["internship", "graduation", "career", "thesis", "startup", "publication", "certificate"]
        for kw in goal_keywords:
            if kw in lower_prompt:
                return {
                    "should_propose_mission": True,
                    "title": f"Achieve goal: {kw.capitalize()}",
                    "objective": f"Systematically plan and execute milestone work for {kw}.",
                    "reason": f"Detected long-term keyword '{kw}'",
                    "confidence": 0.85
                }

        return {"should_propose_mission": False, "reason": "No long-term objective detected."}
