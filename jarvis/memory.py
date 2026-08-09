"""
Memory Management for JARVIS
Handles persistent SQLite storage of profile facts, learned memory, reminders, and task history
"""

import sqlite3
import json
import os
import re
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path


_DB_CONNECTIONS: Dict[str, sqlite3.Connection] = {}
_DB_CONNECTIONS_LOCK = threading.Lock()


def get_shared_db_connection(db_path: str = "jarvis/data/jarvis.db") -> sqlite3.Connection:
    """Get cached shared SQLite database connection with Row factory"""
    global _DB_CONNECTIONS
    norm_path = os.path.normpath(db_path)
    with _DB_CONNECTIONS_LOCK:
        if norm_path not in _DB_CONNECTIONS:
            conn = sqlite3.connect(norm_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            _DB_CONNECTIONS[norm_path] = conn
        return _DB_CONNECTIONS[norm_path]


def close_shared_db_connections():
    """Close all open SQLite connection caches (useful for test cleanup on Windows)."""
    global _DB_CONNECTIONS
    with _DB_CONNECTIONS_LOCK:
        for conn in _DB_CONNECTIONS.values():
            try:
                conn.close()
            except Exception:
                pass
        _DB_CONNECTIONS.clear()


class Memory:
    """Manages JARVIS memory and persistent storage using SQLite"""
    
    def __init__(self, db_path: str = "jarvis/data/jarvis.db"):
        """Initialize SQLite memory system"""
        # If passed legacy file name (e.g. jarvis_memory.json), default to SQLite path
        if db_path.endswith(".json"):
            db_path = "jarvis/data/jarvis.db"
            
        self.db_path = db_path
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._profile_cache: Optional[Dict[str, str]] = None
        self._facts_cache: Optional[Tuple[float, List[Dict]]] = None
        
        self._init_db()
        self._migrate_legacy_json()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with Row factory"""
        return get_shared_db_connection(self.db_path)

    def test_connection(self) -> tuple[bool, str]:
        """Test SQLite database connection with a real query"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM profile")
                count = cursor.fetchone()[0]
                return True, f"Connected to {self.db_path} ({count} profile records)"
        except Exception as e:
            return False, f"Database error: {e}"
    
    def _init_db(self):
        """Initialize database schema with WAL mode enabled for high performance"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                cursor.execute("PRAGMA cache_size=-64000;")
                cursor.execute("PRAGMA temp_store=MEMORY;")
            except Exception:
                pass
            
            # Profile table: static identity facts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profile (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP
                )
            """)
            
            # Facts table: learned user information
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT,
                    content TEXT,
                    source TEXT,
                    created_at TIMESTAMP,
                    confidence TEXT
                )
            """)
            
            # Reminders table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT,
                    due_date TEXT,
                    status TEXT DEFAULT 'pending',
                    completed BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
            """)
            
            # Conversation log: rolling conversation history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT,
                    content TEXT,
                    timestamp TIMESTAMP
                )
            """)
            
            # Notes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT,
                    category TEXT,
                    created_at TIMESTAMP
                )
            """)
            
            # Task history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task TEXT,
                    result TEXT,
                    timestamp TIMESTAMP
                )
            """)
            
            # Flashcards table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flashcards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT,
                    answer TEXT,
                    category TEXT DEFAULT 'general',
                    last_reviewed TIMESTAMP,
                    next_review TIMESTAMP,
                    interval_days INTEGER DEFAULT 1,
                    created_at TIMESTAMP
                )
            """)

            # Deadlines table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deadlines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    due_date TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    last_alerted TIMESTAMP,
                    created_at TIMESTAMP
                )
            """)

            # Ideas table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ideas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    content TEXT,
                    category TEXT DEFAULT 'general',
                    created_at TIMESTAMP
                )
            """)

            # Inventory master table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    sku TEXT PRIMARY KEY,
                    item_name TEXT,
                    quantity INTEGER DEFAULT 0,
                    reorder_threshold INTEGER DEFAULT 10,
                    updated_at TIMESTAMP
                )
            """)

            # Inventory log table for consumption velocity tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inventory_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT,
                    item_name TEXT,
                    quantity_changed INTEGER,
                    event_type TEXT DEFAULT 'sale',
                    timestamp TIMESTAMP
                )
            """)

            # Price watch table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_watch (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    condition TEXT,
                    target_price REAL,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP,
                    triggered_at TIMESTAMP
                )
            """)

            # Trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    action TEXT,
                    price REAL,
                    quantity REAL,
                    reason TEXT,
                    timestamp TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def _migrate_legacy_json(self):
        """Migrate legacy jarvis_memory.json if it exists"""
        json_file = "jarvis_memory.json"
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    legacy_data = json.load(f)
                
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Migrate reminders
                    for r in legacy_data.get("reminders", []):
                        cursor.execute("""
                            INSERT INTO reminders (text, due_date, completed, created_at)
                            VALUES (?, ?, ?, ?)
                        """, (r.get("text", ""), r.get("due_date"), 1 if r.get("completed") else 0, r.get("created_at", datetime.now().isoformat())))
                    
                    # Migrate preferences to profile
                    for k, v in legacy_data.get("preferences", {}).items():
                        cursor.execute("""
                            INSERT OR REPLACE INTO profile (key, value, updated_at)
                            VALUES (?, ?, ?)
                        """, (str(k), str(v), datetime.now().isoformat()))
                    
                    # Migrate notes
                    for n in legacy_data.get("notes", []):
                        cursor.execute("""
                            INSERT INTO notes (text, category, created_at)
                            VALUES (?, ?, ?)
                        """, (n.get("text", ""), n.get("category", "general"), n.get("created_at", datetime.now().isoformat())))
                    
                    # Migrate task history
                    for t in legacy_data.get("task_history", []):
                        cursor.execute("""
                            INSERT INTO task_history (task, result, timestamp)
                            VALUES (?, ?, ?)
                        """, (t.get("task", ""), t.get("result", "completed"), t.get("timestamp", datetime.now().isoformat())))
                    
                    conn.commit()
                
                # Backup legacy json
                os.rename(json_file, f"{json_file}.bak")
            except Exception:
                pass

    # --- Profile Methods ---

    def set_profile_value(self, key: str, value: str):
        """Set or update a profile entry"""
        now = datetime.now().isoformat()
        self._profile_cache = None
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO profile (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, value, now))
            conn.commit()

    def get_profile(self) -> Dict[str, str]:
        """Get all profile key-values with memory caching"""
        if self._profile_cache is not None:
            return self._profile_cache.copy()
        with self._get_connection() as conn:
            rows = conn.execute("SELECT key, value FROM profile").fetchall()
            self._profile_cache = {row["key"]: row["value"] for row in rows}
            return self._profile_cache.copy()

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get preference from profile table for backward compatibility"""
        profile = self.get_profile()
        return profile.get(key, default)

    def set_preference(self, key: str, value: Any):
        """Set preference in profile table for backward compatibility"""
        self.set_profile_value(str(key), str(value))

    # --- Facts Methods ---

    def add_fact(self, category: str, content: str, source: str = "manual", confidence: str = "high") -> Optional[Dict]:
        """
        Add a fact if it's not a duplicate.
        """
        category = category.strip().lower()
        content = content.strip()
        
        if not content:
            return None
            
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Simple deduplication check against existing facts
            existing = cursor.execute("SELECT content FROM facts").fetchall()
            clean_new = re.sub(r'[^\w\s]', '', content.lower())
            
            for row in existing:
                clean_exist = re.sub(r'[^\w\s]', '', row["content"].lower())
                # Exact or high substring match check
                if clean_new == clean_exist or (len(clean_new) > 15 and clean_new in clean_exist):
                    return None
            
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO facts (category, content, source, created_at, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (category, content, source, now, confidence))
            
            fact_id = cursor.lastrowid
            conn.commit()
            self.invalidate_facts_cache()
            
            return {
                "id": fact_id,
                "category": category,
                "content": content,
                "source": source,
                "created_at": now,
                "confidence": confidence
            }

    def invalidate_facts_cache(self):
        """Invalidate in-memory facts cache"""
        self._facts_cache = None

    def get_facts(self, category: Optional[str] = None) -> List[Dict]:
        """Get stored facts with short in-memory caching for uncategorized queries"""
        import time
        now_ts = time.time()
        facts_cache = getattr(self, '_facts_cache', None)
        if not category and facts_cache is not None:
            cache_ts, cached_list = facts_cache
            if (now_ts - cache_ts) < 10.0:  # 10s TTL cache
                return [dict(item) for item in cached_list]

        with self._get_connection() as conn:
            if category:
                rows = conn.execute(
                    "SELECT * FROM facts WHERE LOWER(category) = LOWER(?) ORDER BY id DESC",
                    (category,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM facts ORDER BY id DESC").fetchall()
            
            result = [dict(row) for row in rows]
            if not category:
                self._facts_cache = (now_ts, result)
            return result

    def search_facts(self, keyword: str) -> List[Dict]:
        """Search facts matching keyword"""
        kw = f"%{keyword.strip()}%"
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM facts WHERE content LIKE ? OR category LIKE ? ORDER BY id DESC",
                (kw, kw)
            ).fetchall()
            return [dict(row) for row in rows]

    def delete_facts_by_keyword(self, keyword: str) -> List[Dict]:
        """Delete facts matching keyword and return deleted items"""
        matches = self.search_facts(keyword)
        if not matches:
            return []
        
        ids = [m["id"] for m in matches]
        with self._get_connection() as conn:
            conn.execute(
                f"DELETE FROM facts WHERE id IN ({','.join(['?']*len(ids))})",
                ids
            )
            conn.commit()
        self.invalidate_facts_cache()
        return matches

    def delete_fact_by_id(self, fact_id: int) -> bool:
        """Delete a single fact by ID"""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_top_relevant_facts(self, prompt: str, limit: int = 15) -> List[Dict]:
        """
        Rank and return top relevant facts for context injection.
        Prioritizes recency and keyword matching with prompt words across recent facts.
        """
        facts = self.get_facts()
        if not facts:
            return []
        
        # Limit scoring to top 50 recent facts for speed
        recent_facts = facts[:50]
        prompt_words = set(re.findall(r'\w+', prompt.lower()))
        
        scored_facts = []
        for idx, fact in enumerate(reversed(recent_facts)):  # Recent facts first
            content_words = set(re.findall(r'\w+', fact["content"].lower()))
            overlap = len(prompt_words.intersection(content_words))
            # Base score + overlap bonus + recency bonus
            score = overlap * 3 + (idx * 0.1)
            scored_facts.append((score, fact))
        
        scored_facts.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored_facts[:limit]]

    # --- Conversation Log Methods ---

    def log_conversation_message(self, role: str, content: str):
        """Log conversation turn to DB"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO conversation_log (role, content, timestamp)
                VALUES (?, ?, ?)
            """, (role, content, datetime.now().isoformat()))
            conn.commit()

    # --- Reminders Methods ---

    def add_reminder(self, text: str, due_date: Optional[str] = None) -> Dict:
        """Add a reminder"""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reminders (text, due_date, status, completed, created_at)
                VALUES (?, ?, 'pending', 0, ?)
            """, (text, due_date, now))
            reminder_id = cursor.lastrowid
            conn.commit()
            return {
                "id": reminder_id,
                "text": text,
                "due_date": due_date,
                "created_at": now,
                "completed": False
            }

    def get_reminders(self) -> List[Dict]:
        """Get all reminders"""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM reminders ORDER BY id ASC").fetchall()
            result = []
            for row in rows:
                r = dict(row)
                r["completed"] = bool(r.get("completed", 0))
                result.append(r)
            return result

    def get_pending_reminders(self) -> List[Dict]:
        """Get all pending/uncompleted reminders"""
        reminders = self.get_reminders()
        return [r for r in reminders if not r.get("completed")]

    def get_fact_count(self) -> int:
        """Get total count of facts stored in DB"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM facts")
                return cursor.fetchone()[0]
        except Exception:
            return 0

    def complete_reminder(self, reminder_id: int) -> bool:
        """Mark reminder completed"""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute("""
                UPDATE reminders
                SET completed = 1, status = 'completed', completed_at = ?
                WHERE id = ?
            """, (now, reminder_id))
            conn.commit()
            return cursor.rowcount > 0

    def clear_all_pending_reminders(self) -> int:
        """Mark all pending reminders as completed / cleared"""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute("""
                UPDATE reminders
                SET completed = 1, status = 'completed', completed_at = ?
                WHERE completed = 0 OR status = 'pending'
            """, (now,))
            conn.commit()
            return cursor.rowcount

    # --- Notes Methods ---

    def add_note(self, text: str, category: str = "general") -> Dict:
        """Add a note"""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notes (text, category, created_at)
                VALUES (?, ?, ?)
            """, (text, category, now))
            note_id = cursor.lastrowid
            conn.commit()
            return {
                "id": note_id,
                "text": text,
                "category": category,
                "created_at": now
            }

    def get_notes(self, category: Optional[str] = None) -> List[Dict]:
        """Get notes"""
        with self._get_connection() as conn:
            if category:
                rows = conn.execute("SELECT * FROM notes WHERE category = ?", (category,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM notes ORDER BY id ASC").fetchall()
            return [dict(row) for row in rows]

    # --- Task History Methods ---

    def log_task(self, task: str, result: str = "completed"):
        """Log executed task"""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO task_history (task, result, timestamp)
                VALUES (?, ?, ?)
            """, (task, result, now))
            conn.commit()

    def get_recent_tasks(self, limit: int = 10) -> List[Dict]:
        """Get recent tasks"""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM task_history ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(row) for row in reversed(rows)]

    # --- Flashcards Methods ---

    def add_flashcard(self, question: str, answer: str, category: str = "general") -> Dict:
        """Add a flashcard to SQLite database"""
        now = datetime.now()
        now_iso = now.isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO flashcards (question, answer, category, next_review, interval_days, created_at)
                VALUES (?, ?, ?, ?, 1, ?)
            """, (question.strip(), answer.strip(), category.strip().lower(), now_iso, now_iso))
            card_id = cursor.lastrowid
            conn.commit()
            return {
                "id": card_id,
                "question": question,
                "answer": answer,
                "category": category,
                "next_review": now_iso,
                "interval_days": 1
            }

    def get_due_flashcards(self, category: Optional[str] = None) -> List[Dict]:
        """Get flashcards due for review"""
        now_iso = datetime.now().isoformat()
        with self._get_connection() as conn:
            if category:
                rows = conn.execute(
                    "SELECT * FROM flashcards WHERE (next_review <= ? OR next_review IS NULL) AND LOWER(category) = LOWER(?) ORDER BY id ASC",
                    (now_iso, category)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM flashcards WHERE next_review <= ? OR next_review IS NULL ORDER BY id ASC",
                    (now_iso,)
                ).fetchall()
            return [dict(row) for row in rows]

    def update_flashcard_review(self, card_id: int, correct: bool):
        """Update flashcard spaced repetition interval"""
        from datetime import timedelta
        now = datetime.now()
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM flashcards WHERE id = ?", (card_id,)).fetchone()
            if not row:
                return
            card = dict(row)
            current_interval = card.get("interval_days", 1) or 1
            if correct:
                new_interval = current_interval * 2
            else:
                new_interval = 1
            next_review = (now + timedelta(days=new_interval)).isoformat()
            conn.execute("""
                UPDATE flashcards
                SET last_reviewed = ?, next_review = ?, interval_days = ?
                WHERE id = ?
            """, (now.isoformat(), next_review, new_interval, card_id))
            conn.commit()

    # --- Deadlines Methods ---

    def add_deadline(self, name: str, due_date_iso: str) -> Dict:
        """Add a deadline to SQLite database"""
        now_iso = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO deadlines (name, due_date, status, created_at)
                VALUES (?, ?, 'pending', ?)
            """, (name.strip(), due_date_iso, now_iso))
            deadline_id = cursor.lastrowid
            conn.commit()
            return {
                "id": deadline_id,
                "name": name,
                "due_date": due_date_iso,
                "status": "pending"
            }

    def get_pending_deadlines(self) -> List[Dict]:
        """Get pending deadlines ordered by due date"""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM deadlines WHERE status = 'pending' ORDER BY due_date ASC").fetchall()
            return [dict(row) for row in rows]

    def update_deadline_last_alerted(self, deadline_id: int):
        """Update deadline last_alerted timestamp"""
        now_iso = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("UPDATE deadlines SET last_alerted = ? WHERE id = ?", (now_iso, deadline_id))
            conn.commit()

    def complete_deadline(self, deadline_id: int):
        """Mark deadline completed"""
        with self._get_connection() as conn:
            conn.execute("UPDATE deadlines SET status = 'completed' WHERE id = ?", (deadline_id,))
            conn.commit()

    # --- Ideas Methods ---

    def add_idea(self, content: str, title: str = "", category: str = "general") -> Dict:
        """Add an idea/decision to SQLite database"""
        now_iso = datetime.now().isoformat()
        if not title:
            words = content.strip().split()
            title = " ".join(words[:5]) + "..." if len(words) > 5 else content.strip()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ideas (title, content, category, created_at)
                VALUES (?, ?, ?, ?)
            """, (title, content.strip(), category.strip(), now_iso))
            idea_id = cursor.lastrowid
            conn.commit()
            return {
                "id": idea_id,
                "title": title,
                "content": content,
                "category": category,
                "created_at": now_iso
            }

    def get_ideas(self, category: Optional[str] = None) -> List[Dict]:
        """Get all ideas"""
        with self._get_connection() as conn:
            if category:
                rows = conn.execute("SELECT * FROM ideas WHERE category = ? ORDER BY id DESC", (category,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM ideas ORDER BY id DESC").fetchall()
            return [dict(row) for row in rows]

    def search_ideas(self, keyword: str) -> List[Dict]:
        """Search ideas matching keyword"""
        kw = f"%{keyword.strip()}%"
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM ideas WHERE title LIKE ? OR content LIKE ? ORDER BY id DESC", (kw, kw)).fetchall()
            return [dict(row) for row in rows]

    # --- Price Watch Methods ---

    def add_price_watch(self, ticker: str, condition: str, target_price: float) -> Dict:
        """Add price watch alert"""
        now_iso = datetime.now().isoformat()
        ticker = ticker.strip().upper()
        condition = condition.strip().lower()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO price_watch (ticker, condition, target_price, status, created_at)
                VALUES (?, ?, ?, 'active', ?)
            """, (ticker, condition, target_price, now_iso))
            watch_id = cursor.lastrowid
            conn.commit()
            return {
                "id": watch_id,
                "ticker": ticker,
                "condition": condition,
                "target_price": target_price,
                "status": "active",
                "created_at": now_iso
            }

    def get_active_price_watches(self) -> List[Dict]:
        """Get active price watches"""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM price_watch WHERE status = 'active' ORDER BY id ASC").fetchall()
            return [dict(row) for row in rows]

    def trigger_price_watch(self, watch_id: int):
        """Mark price watch triggered"""
        now_iso = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute("UPDATE price_watch SET status = 'triggered', triggered_at = ? WHERE id = ?", (now_iso, watch_id))
            conn.commit()

    # --- Trades Methods ---

    def add_trade(self, ticker: str, action: str, price: float, quantity: float, reason: str = "") -> Dict:
        """Log a trade"""
        now_iso = datetime.now().isoformat()
        ticker = ticker.strip().upper()
        action = action.strip().upper()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trades (ticker, action, price, quantity, reason, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ticker, action, price, quantity, reason.strip(), now_iso))
            trade_id = cursor.lastrowid
            conn.commit()
            return {
                "id": trade_id,
                "ticker": ticker,
                "action": action,
                "price": price,
                "quantity": quantity,
                "reason": reason,
                "timestamp": now_iso
            }

    def get_trades(self, ticker: Optional[str] = None) -> List[Dict]:
        """Get trade journal logs"""
        with self._get_connection() as conn:
            if ticker:
                rows = conn.execute("SELECT * FROM trades WHERE UPPER(ticker) = UPPER(?) ORDER BY id DESC", (ticker,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM trades ORDER BY id DESC").fetchall()
            return [dict(row) for row in rows]

    # --- Inventory Methods ---

    def log_inventory_event(
        self,
        sku: str,
        item_name: str,
        quantity_changed: int,
        event_type: str = "sale",
        reorder_threshold: int = 10,
        timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """Log inventory consumption/restock event and update current stock."""
        now_iso = timestamp or datetime.now().isoformat()
        sku_clean = sku.strip().upper()
        item_clean = item_name.strip()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Fetch current stock if exists
            row = cursor.execute("SELECT quantity, reorder_threshold FROM inventory WHERE sku = ?", (sku_clean,)).fetchone()
            current_qty = row["quantity"] if row else 0
            new_threshold = reorder_threshold if reorder_threshold is not None else (row["reorder_threshold"] if row else 10)
            
            # quantity_changed is negative for consumption/sales, positive for restocks
            new_qty = max(0, current_qty + quantity_changed)
            
            cursor.execute("""
                INSERT INTO inventory (sku, item_name, quantity, reorder_threshold, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(sku) DO UPDATE SET
                    item_name = excluded.item_name,
                    quantity = excluded.quantity,
                    reorder_threshold = excluded.reorder_threshold,
                    updated_at = excluded.updated_at
            """, (sku_clean, item_clean, new_qty, new_threshold, now_iso))
            
            cursor.execute("""
                INSERT INTO inventory_log (sku, item_name, quantity_changed, event_type, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (sku_clean, item_clean, quantity_changed, event_type, now_iso))
            
            conn.commit()
            return {
                "sku": sku_clean,
                "item_name": item_clean,
                "previous_quantity": current_qty,
                "new_quantity": new_qty,
                "reorder_threshold": new_threshold,
                "quantity_changed": quantity_changed,
                "event_type": event_type,
                "timestamp": now_iso
            }

    def get_inventory_item(self, sku: str) -> Optional[Dict[str, Any]]:
        """Get inventory details for a single SKU."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM inventory WHERE sku = ?", (sku.strip().upper(),)).fetchone()
            return dict(row) if row else None

    def get_all_inventory(self) -> List[Dict[str, Any]]:
        """Get list of all inventory items."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM inventory ORDER BY item_name ASC").fetchall()
            return [dict(row) for row in rows]

    def get_inventory_logs(self, sku: Optional[str] = None, days: int = 30) -> List[Dict[str, Any]]:
        """Get inventory transaction log entries."""
        with self._get_connection() as conn:
            if sku:
                rows = conn.execute("""
                    SELECT * FROM inventory_log 
                    WHERE UPPER(sku) = UPPER(?) 
                    ORDER BY id DESC
                """, (sku.strip(),)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM inventory_log ORDER BY id DESC").fetchall()
            return [dict(row) for row in rows]


class CommandLogger:
    """Logs all executed commands for safety and audit"""
    
    def __init__(self, log_file: str = "jarvis_commands.log"):
        """Initialize command logger"""
        self.log_file = log_file
    
    def log(self, command: str, approved: bool = True, result: str = ""):
        """Log a command execution"""
        timestamp = datetime.now().isoformat()
        entry = f"[{timestamp}] Command: {command} | Approved: {approved} | Result: {result}\n"
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(entry)
    
    def get_recent_logs(self, limit: int = 20) -> List[str]:
        """Get recent command logs"""
        if not os.path.exists(self.log_file):
            return []
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        return lines[-limit:]


# Backward compatibility alias
MemoryManager = Memory

