"""
TaskTracker for JARVIS Mk4 Agentic Layer
Tracks task lifecycle, assigned agents, subtask dependencies, and execution state.
"""

import uuid
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@dataclass
class TaskItem:
    task_id: str
    description: str
    assigned_agent: str = "Unassigned"
    parent_task_id: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    current_step: str = ""
    result: Optional[str] = None
    error: Optional[str] = None
    iteration_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "parent_task_id": self.parent_task_id,
            "description": self.description,
            "assigned_agent": self.assigned_agent,
            "status": self.status.value if isinstance(self.status, TaskStatus) else str(self.status),
            "current_step": self.current_step,
            "result": self.result,
            "error": self.error,
            "iteration_count": self.iteration_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


class TaskTracker:
    """Lightweight in-memory task tracker for multi-agent workflows."""

    def __init__(self):
        self.tasks: Dict[str, TaskItem] = {}

    def create_task(
        self,
        description: str,
        assigned_agent: str = "Unassigned",
        parent_task_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TaskItem:
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task = TaskItem(
            task_id=task_id,
            description=description,
            assigned_agent=assigned_agent,
            parent_task_id=parent_task_id,
            status=TaskStatus.PENDING,
            metadata=metadata or {}
        )
        self.tasks[task_id] = task
        return task

    def update_task(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        current_step: Optional[str] = None,
        result: Optional[str] = None,
        error: Optional[str] = None,
        increment_iteration: bool = False
    ) -> Optional[TaskItem]:
        task = self.tasks.get(task_id)
        if not task:
            return None

        if status is not None:
            task.status = status
        if current_step is not None:
            task.current_step = current_step
        if result is not None:
            task.result = result
        if error is not None:
            task.error = error
        if increment_iteration:
            task.iteration_count += 1

        task.updated_at = time.time()
        return task

    def get_task(self, task_id: str) -> Optional[TaskItem]:
        return self.tasks.get(task_id)

    def get_subtasks(self, parent_task_id: str) -> List[TaskItem]:
        return [t for t in self.tasks.values() if t.parent_task_id == parent_task_id]

    def list_all_tasks(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self.tasks.values()]
