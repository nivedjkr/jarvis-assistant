"""
Project Database Manager for JARVIS
Handles SQLite persistent storage and reasoning for all user projects across
personal, client, startup, study, and trading categories.
"""

import sqlite3
import os
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any, Optional, Union


class ProjectManager:
    """Manages project data, tasks, notes, decisions, timelines, and links in jarvis.db"""

    def __init__(self, db_path: str = "jarvis/data/jarvis.db"):
        self.db_path = db_path
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with Row factory"""
        from jarvis.memory import get_shared_db_connection
        return get_shared_db_connection(self.db_path)

    def _init_db(self):
        """Initialize project database schema and pre-populate sample data if empty"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Projects table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    status TEXT DEFAULT 'active',
                    description TEXT,
                    category TEXT,
                    priority INTEGER DEFAULT 3,
                    tech_stack TEXT,
                    repo_url TEXT,
                    deploy_url TEXT,
                    start_date TEXT,
                    deadline TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. Project Tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    status TEXT DEFAULT 'todo',
                    priority INTEGER DEFAULT 3,
                    due_date TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)

            # 3. Project Notes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                    content TEXT NOT NULL,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 4. Project Decisions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                    decision TEXT NOT NULL,
                    reasoning TEXT,
                    outcome TEXT,
                    date TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 5. Project Links table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                    label TEXT,
                    url TEXT NOT NULL,
                    type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 6. Project Timeline table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_timeline (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                    event TEXT NOT NULL,
                    date TEXT,
                    type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 7. Project People table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS project_people (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
                    name TEXT,
                    role TEXT,
                    contact TEXT,
                    notes TEXT
                )
            """)
            conn.commit()

        # Seed sample project if database table is completely empty
        self._seed_sample_project_if_empty()

    def _seed_sample_project_if_empty(self):
        """Pre-populate with JARVIS Assistant sample project on initial run if projects table is empty"""
        projects = self.get_all_projects()
        if not projects:
            p_id = self.create_project(
                name="JARVIS Assistant",
                description="Personal AI Assistant with voice control, local automation, trading journal, study tools, and project management",
                category="personal",
                tech_stack="Python, SQLite, Rich, OpenAI API",
                priority=5,
                repo_url="https://github.com/nivedjkr/jarvis-assistant",
                start_date=date.today().isoformat()
            )
            if p_id:
                self.add_task(
                    project_id=p_id,
                    title="Add comprehensive project database to JARVIS",
                    priority=5,
                    due_date=date.today().isoformat(),
                    notes="SQLite backed database with proactive intelligence and context injection"
                )
                self.add_timeline_event(
                    project_id=p_id,
                    event="JARVIS Project Management Subsystem Initialized",
                    type_str="launch",
                    date_str=date.today().isoformat()
                )

    # ==================== HELPER RESOLVER ====================

    def resolve_project_id(self, name_or_id: Union[str, int]) -> Optional[int]:
        """Resolve a project name or ID to an integer project ID"""
        if isinstance(name_or_id, int):
            return name_or_id
        
        name_str = str(name_or_id).strip()
        if name_str.isdigit():
            return int(name_str)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Exact match (case insensitive)
            cursor.execute("SELECT id FROM projects WHERE LOWER(name) = LOWER(?)", (name_str,))
            row = cursor.fetchone()
            if row:
                return row["id"]

            # Partial substring match
            cursor.execute("SELECT id FROM projects WHERE LOWER(name) LIKE LOWER(?) ORDER BY LENGTH(name) ASC", (f"%{name_str}%",))
            row = cursor.fetchone()
            if row:
                return row["id"]

        return None

    # ==================== READ FUNCTIONS ====================

    def get_all_projects(self, status: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all projects with task breakdown counts"""
        query = "SELECT * FROM projects WHERE 1=1"
        params = []

        if status:
            if status.lower() == "active":
                query += " AND LOWER(status) = 'active'"
            else:
                query += " AND LOWER(status) = LOWER(?)"
                params.append(status)
        if category:
            query += " AND LOWER(category) = LOWER(?)"
            params.append(category)

        query += " ORDER BY priority DESC, created_at DESC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            projects = [dict(row) for row in cursor.fetchall()]

            for p in projects:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_tasks,
                        SUM(CASE WHEN status != 'done' THEN 1 ELSE 0 END) as open_tasks,
                        SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as completed_tasks
                    FROM project_tasks WHERE project_id = ?
                """, (p["id"],))
                counts = cursor.fetchone()
                p["total_tasks"] = counts["total_tasks"] or 0
                p["open_tasks"] = counts["open_tasks"] or 0
                p["completed_tasks"] = counts["completed_tasks"] or 0

        return projects

    def get_project(self, name_or_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """Get full project details including tasks, notes, decisions, links, timeline, and people"""
        p_id = self.resolve_project_id(name_or_id)
        if not p_id:
            return None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM projects WHERE id = ?", (p_id,))
            row = cursor.fetchone()
            if not row:
                return None

            project = dict(row)

            # Tasks
            cursor.execute("SELECT * FROM project_tasks WHERE project_id = ? ORDER BY status ASC, priority DESC, created_at DESC", (p_id,))
            project["tasks"] = [dict(r) for r in cursor.fetchall()]

            # Notes
            cursor.execute("SELECT * FROM project_notes WHERE project_id = ? ORDER BY created_at DESC", (p_id,))
            project["notes"] = [dict(r) for r in cursor.fetchall()]

            # Decisions
            cursor.execute("SELECT * FROM project_decisions WHERE project_id = ? ORDER BY created_at DESC", (p_id,))
            project["decisions"] = [dict(r) for r in cursor.fetchall()]

            # Links
            cursor.execute("SELECT * FROM project_links WHERE project_id = ? ORDER BY created_at DESC", (p_id,))
            project["links"] = [dict(r) for r in cursor.fetchall()]

            # Timeline
            cursor.execute("SELECT * FROM project_timeline WHERE project_id = ? ORDER BY date DESC, created_at DESC", (p_id,))
            project["timeline"] = [dict(r) for r in cursor.fetchall()]

            # People
            cursor.execute("SELECT * FROM project_people WHERE project_id = ?", (p_id,))
            project["people"] = [dict(r) for r in cursor.fetchall()]

            # Task counts
            project["total_tasks"] = len(project["tasks"])
            project["open_tasks"] = len([t for t in project["tasks"] if t["status"] != "done"])
            project["completed_tasks"] = len([t for t in project["tasks"] if t["status"] == "done"])

            return project

    def get_project_tasks(self, project_id: Union[str, int], status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all tasks for a project, optionally filtered by status"""
        p_id = self.resolve_project_id(project_id)
        if not p_id:
            return []

        query = "SELECT * FROM project_tasks WHERE project_id = ?"
        params: List[Any] = [p_id]

        if status:
            query += " AND LOWER(status) = LOWER(?)"
            params.append(status)

        query += " ORDER BY priority DESC, created_at DESC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_project_timeline(self, project_id: Union[str, int]) -> List[Dict[str, Any]]:
        """Get chronological events for a project"""
        p_id = self.resolve_project_id(project_id)
        if not p_id:
            return []

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM project_timeline WHERE project_id = ? ORDER BY date ASC, created_at ASC", (p_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_project_decisions(self, project_id: Union[str, int]) -> List[Dict[str, Any]]:
        """Get decisions logged for a project"""
        p_id = self.resolve_project_id(project_id)
        if not p_id:
            return []

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM project_decisions WHERE project_id = ? ORDER BY created_at DESC", (p_id,))
            return [dict(row) for row in cursor.fetchall()]

    def search_projects(self, query: str) -> List[Dict[str, Any]]:
        """Search projects across name, description, category, tech_stack, and notes"""
        search_term = f"%{query.strip()}%"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT p.* FROM projects p
                LEFT JOIN project_notes n ON p.id = n.project_id
                LEFT JOIN project_tasks t ON p.id = t.project_id
                WHERE p.name LIKE ? 
                   OR p.description LIKE ? 
                   OR p.category LIKE ? 
                   OR p.tech_stack LIKE ?
                   OR n.content LIKE ?
                   OR t.title LIKE ?
                ORDER BY p.priority DESC
            """, (search_term, search_term, search_term, search_term, search_term, search_term))
            return [dict(row) for row in cursor.fetchall()]

    def get_overdue_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks past due_date across ALL projects where status is not 'done'"""
        today_str = date.today().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.*, p.name as project_name
                FROM project_tasks t
                JOIN projects p ON t.project_id = p.id
                WHERE t.status != 'done'
                  AND t.due_date IS NOT NULL
                  AND t.due_date != ''
                  AND t.due_date < ?
                ORDER BY t.due_date ASC
            """, (today_str,))
            return [dict(row) for row in cursor.fetchall()]

    def get_active_projects_summary(self) -> List[Dict[str, Any]]:
        """Get brief status of all active projects"""
        return self.get_all_projects(status="active")

    # ==================== WRITE FUNCTIONS ====================

    def create_project(
        self,
        name: str,
        description: str = "",
        category: str = "personal",
        tech_stack: str = "",
        deadline: str = "",
        repo_url: str = "",
        priority: int = 3,
        deploy_url: str = "",
        start_date: Optional[str] = None
    ) -> Optional[int]:
        """Create a new project in DB"""
        start = start_date or date.today().isoformat()
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO projects 
                    (name, description, category, priority, tech_stack, repo_url, deploy_url, start_date, deadline, last_updated, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, description, category, priority, tech_stack, repo_url, deploy_url, start, deadline, now_ts, now_ts))
                p_id = cursor.lastrowid

                # Initial timeline event
                cursor.execute("""
                    INSERT INTO project_timeline (project_id, event, date, type, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (p_id, f"Project '{name}' created", start, "milestone", now_ts))

                conn.commit()
                return p_id
            except sqlite3.IntegrityError:
                # Project with this name already exists
                return None

    def update_project(self, project_id: Union[str, int], **kwargs) -> bool:
        """Update any project field dynamically"""
        p_id = self.resolve_project_id(project_id)
        if not p_id:
            return False

        allowed_fields = {
            "name", "status", "description", "category", "priority",
            "tech_stack", "repo_url", "deploy_url", "start_date", "deadline"
        }

        updates = []
        params = []
        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                updates.append(f"{field} = ?")
                params.append(value)

        if not updates:
            return False

        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updates.append("last_updated = ?")
        params.append(now_ts)
        params.append(p_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE projects SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
            return cursor.rowcount > 0

    def add_task(
        self,
        project_id: Union[str, int],
        title: str,
        priority: int = 3,
        due_date: str = "",
        notes: str = ""
    ) -> Optional[int]:
        """Add a task to a project"""
        p_id = self.resolve_project_id(project_id)
        if not p_id:
            return None

        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO project_tasks (project_id, title, priority, due_date, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (p_id, title, priority, due_date, notes, now_ts))
            task_id = cursor.lastrowid
            
            # Touch project last_updated
            cursor.execute("UPDATE projects SET last_updated = ? WHERE id = ?", (now_ts, p_id))
            conn.commit()
            return task_id

    def update_task(
        self,
        task_id: int,
        status: Optional[str] = None,
        notes: Optional[str] = None,
        title: Optional[str] = None,
        due_date: Optional[str] = None
    ) -> bool:
        """Update task details or status (e.g. mark done)"""
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updates = []
        params = []

        if status:
            updates.append("status = ?")
            params.append(status.lower())
            if status.lower() == "done":
                updates.append("completed_at = ?")
                params.append(now_ts)

        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if due_date is not None:
            updates.append("due_date = ?")
            params.append(due_date)

        if not updates:
            return False

        params.append(task_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Fetch project_id to update project last_updated
            cursor.execute("SELECT project_id FROM project_tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return False

            p_id = row["project_id"]
            cursor.execute(f"UPDATE project_tasks SET {', '.join(updates)} WHERE id = ?", params)
            cursor.execute("UPDATE projects SET last_updated = ? WHERE id = ?", (now_ts, p_id))
            conn.commit()
            return True

    def find_task_by_title(self, project_id: Union[str, int], title_query: str) -> Optional[Dict[str, Any]]:
        """Find a task in a project matching title query"""
        p_id = self.resolve_project_id(project_id)
        if not p_id:
            return None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM project_tasks WHERE project_id = ? AND LOWER(title) LIKE LOWER(?) ORDER BY id DESC", (p_id, f"%{title_query}%"))
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_note(self, project_id: Union[str, int], content: str, tags: str = "") -> Optional[int]:
        """Add a note to a project"""
        p_id = self.resolve_project_id(project_id)
        if not p_id:
            return None

        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO project_notes (project_id, content, tags, created_at)
                VALUES (?, ?, ?, ?)
            """, (p_id, content, tags, now_ts))
            note_id = cursor.lastrowid
            cursor.execute("UPDATE projects SET last_updated = ? WHERE id = ?", (now_ts, p_id))
            conn.commit()
            return note_id

    def add_decision(self, project_id: Union[str, int], decision: str, reasoning: str = "", date_str: Optional[str] = None) -> Optional[int]:
        """Add a decision log to a project"""
        p_id = self.resolve_project_id(project_id)
        if not p_id:
            return None

        d_date = date_str or date.today().isoformat()
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO project_decisions (project_id, decision, reasoning, date, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (p_id, decision, reasoning, d_date, now_ts))
            dec_id = cursor.lastrowid
            cursor.execute("UPDATE projects SET last_updated = ? WHERE id = ?", (now_ts, p_id))
            conn.commit()
            return dec_id

    def update_decision_outcome(self, decision_id: int, outcome: str) -> bool:
        """Update decision outcome"""
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT project_id FROM project_decisions WHERE id = ?", (decision_id,))
            row = cursor.fetchone()
            if not row:
                return False

            p_id = row["project_id"]
            cursor.execute("UPDATE project_decisions SET outcome = ? WHERE id = ?", (outcome, decision_id))
            cursor.execute("UPDATE projects SET last_updated = ? WHERE id = ?", (now_ts, p_id))
            conn.commit()
            return True

    def add_timeline_event(self, project_id: Union[str, int], event: str, type_str: str = "update", date_str: Optional[str] = None, type: Optional[str] = None) -> Optional[int]:
        """Add event to project timeline"""
        p_id = self.resolve_project_id(project_id)
        if not p_id:
            return None

        event_type = type or type_str
        t_date = date_str or date.today().isoformat()
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO project_timeline (project_id, event, date, type, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (p_id, event, t_date, event_type, now_ts))
            event_id = cursor.lastrowid
            cursor.execute("UPDATE projects SET last_updated = ? WHERE id = ?", (now_ts, p_id))
            conn.commit()
            return event_id

    def add_link(self, project_id: Union[str, int], label: str, url: str, link_type: str = "doc") -> Optional[int]:
        """Add link to project"""
        p_id = self.resolve_project_id(project_id)
        if not p_id:
            return None

        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO project_links (project_id, label, url, type, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (p_id, label, url, link_type, now_ts))
            link_id = cursor.lastrowid
            cursor.execute("UPDATE projects SET last_updated = ? WHERE id = ?", (now_ts, p_id))
            conn.commit()
            return link_id

    def add_person(self, project_id: Union[str, int], name: str, role: str = "collaborator", contact: str = "", notes: str = "") -> Optional[int]:
        """Add contact/person associated with project"""
        p_id = self.resolve_project_id(project_id)
        if not p_id:
            return None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO project_people (project_id, name, role, contact, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (p_id, name, role, contact, notes))
            conn.commit()
            return cursor.lastrowid

    def complete_project(self, project_id: Union[str, int]) -> bool:
        """Mark a project as completed and add milestone event to timeline"""
        p_id = self.resolve_project_id(project_id)
        if not p_id:
            return False

        today_str = date.today().isoformat()
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE projects SET status = 'completed', last_updated = ? WHERE id = ?", (now_ts, p_id))
            cursor.execute("""
                INSERT INTO project_timeline (project_id, event, date, type, created_at)
                VALUES (?, ?, ?, 'milestone', ?)
            """, (p_id, "Project completed", today_str, now_ts))
            conn.commit()
            return True

    # ==================== ADVANCED REASONING & WEEKLY REVIEW ====================

    def get_stale_projects(self, days_threshold: int = 14) -> List[Dict[str, Any]]:
        """Get active projects that have had no updates in days_threshold days"""
        cutoff_date = (date.today() - timedelta(days=days_threshold)).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM projects
                WHERE status = 'active'
                  AND (last_updated < ? OR last_updated IS NULL)
                ORDER BY last_updated ASC
            """, (cutoff_date,))
            return [dict(row) for row in cursor.fetchall()]

    def get_approaching_deadlines(self, days_threshold: int = 7) -> List[Dict[str, Any]]:
        """Get active projects with deadlines within next days_threshold days"""
        today_str = date.today().isoformat()
        future_str = (date.today() + timedelta(days=days_threshold)).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM projects
                WHERE status = 'active'
                  AND deadline IS NOT NULL
                  AND deadline != ''
                  AND deadline >= ?
                  AND deadline <= ?
                ORDER BY deadline ASC
            """, (today_str, future_str))
            return [dict(row) for row in cursor.fetchall()]

    def generate_weekly_project_review(self, output_dir: str = "jarvis/data") -> Dict[str, Any]:
        """Generate weekly project review and save as markdown file"""
        from datetime import timedelta
        today = date.today()
        one_week_ago = (today - timedelta(days=7)).isoformat()

        active_projects = self.get_active_projects_summary()
        overdue_tasks = self.get_overdue_tasks()

        # Completed tasks this week
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.*, p.name as project_name
                FROM project_tasks t
                JOIN projects p ON t.project_id = p.id
                WHERE t.status = 'done'
                  AND t.completed_at >= ?
                ORDER BY t.completed_at DESC
            """, (one_week_ago,))
            completed_this_week = [dict(row) for row in cursor.fetchall()]

        # Highest priority active project
        highest_priority_project = active_projects[0]["name"] if active_projects else "None"

        # Unique projects with overdue tasks
        overdue_projects = len(set(t["project_name"] for t in overdue_tasks))

        review_spoken = (
            f"Sir, weekly project review. {len(active_projects)} active projects. "
            f"Completed this week: {len(completed_this_week)} tasks. "
            f"Overdue: {len(overdue_tasks)} tasks across {overdue_projects} projects. "
            f"Biggest priority this week: {highest_priority_project}."
        )

        md_content = [
            f"# Weekly Project Review ({today.isoformat()})",
            f"",
            f"**Active Projects:** {len(active_projects)}",
            f"**Completed Tasks This Week:** {len(completed_this_week)}",
            f"**Overdue Tasks:** {len(overdue_tasks)} across {overdue_projects} projects",
            f"**Highest Priority Project:** {highest_priority_project}",
            f"",
            f"## Active Projects",
        ]
        for p in active_projects:
            md_content.append(f"- **{p['name']}** [{p['category'].upper()}] - Priority {p['priority']} | Open Tasks: {p['open_tasks']} / Total: {p['total_tasks']}")
            if p.get('deadline'):
                md_content.append(f"  *Deadline:* {p['deadline']}")

        md_content.append("")
        md_content.append("## Tasks Completed This Week")
        if completed_this_week:
            for ct in completed_this_week:
                md_content.append(f"- [x] **{ct['title']}** ({ct['project_name']}) - Done at {ct.get('completed_at', '')}")
        else:
            md_content.append("- No tasks completed this week.")

        md_content.append("")
        md_content.append("## Overdue Tasks")
        if overdue_tasks:
            for ot in overdue_tasks:
                md_content.append(f"- [ ] ⚠️ **{ot['title']}** ({ot['project_name']}) - Due: {ot['due_date']}")
        else:
            md_content.append("- No overdue tasks.")

        # Save to jarvis/data/project_review_<date>.md
        out_path = Path(output_dir) / f"project_review_{today.isoformat()}.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_content))

        return {
            "spoken_summary": review_spoken,
            "file_path": str(out_path.resolve()),
            "active_count": len(active_projects),
            "completed_count": len(completed_this_week),
            "overdue_count": len(overdue_tasks)
        }

    # ==================== CONTEXT INJECTION HELPER ====================

    def get_project_context_for_message(self, user_message: str) -> Optional[str]:
        """Check if user message mentions any project in DB and return real project details context"""
        msg_lower = user_message.lower()
        projects = self.get_all_projects()

        matched_project = None
        for p in projects:
            p_name = p["name"].lower()
            # Match project name or key tokens (e.g. "TestApp", "JARVIS")
            if p_name in msg_lower or (len(p_name) > 3 and p_name.split()[0] in msg_lower):
                matched_project = p
                break

        if not matched_project:
            return None

        full_proj = self.get_project(matched_project["id"])
        if not full_proj:
            return None

        context_lines = [
            f"=== REAL PROJECT DATABASE CONTEXT: {full_proj['name']} ===",
            f"Status: {full_proj['status']} | Category: {full_proj['category']} | Priority: {full_proj['priority']}",
            f"Description: {full_proj.get('description') or 'N/A'}",
            f"Tech Stack: {full_proj.get('tech_stack') or 'N/A'}",
            f"Repo: {full_proj.get('repo_url') or 'N/A'} | Deadline: {full_proj.get('deadline') or 'N/A'}",
            f"Tasks Breakdown: {full_proj['open_tasks']} open, {full_proj['completed_tasks']} completed out of {full_proj['total_tasks']} total",
        ]

        # List open tasks
        open_tasks = [t for t in full_proj.get("tasks", []) if t["status"] != "done"]
        if open_tasks:
            context_lines.append("Open Tasks:")
            for t in open_tasks[:5]:
                due_info = f" (Due: {t['due_date']})" if t.get("due_date") else ""
                context_lines.append(f"  - [{t['status'].upper()}] {t['title']}{due_info}")

        # List recent notes
        notes = full_proj.get("notes", [])
        if notes:
            context_lines.append("Recent Notes:")
            for n in notes[:3]:
                context_lines.append(f"  - {n['content']}")

        # List decisions
        decisions = full_proj.get("decisions", [])
        if decisions:
            context_lines.append("Decisions Logged:")
            for d in decisions[:3]:
                reasoning_info = f" (Reasoning: {d['reasoning']})" if d.get("reasoning") else ""
                context_lines.append(f"  - Decision: {d['decision']}{reasoning_info}")

        context_lines.append("CRITICAL: You MUST answer using only this real DB project context. Do not invent or approximate details.")
        return "\n".join(context_lines)


def get_active_projects_summary() -> List[Dict[str, Any]]:
    """Helper function to get active projects summary using default ProjectManager"""
    pm = ProjectManager()
    return pm.get_active_projects_summary()

