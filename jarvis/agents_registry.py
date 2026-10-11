"""
Multi-Agent Persona Registry for JARVIS Mark 5.9.
Orchestrates isolated and coordinated agent identities:
- JARVIS (Butler & General Assistant)
- ULTRON (Autonomous Architect & Offensive Debugger)
- FRIDAY (Tactical HUD & Rapid Research Liaison)
- EDITH (Strategic Sentinel & Perimeter Security)
- KAREN (Workshop Supervisor & Telemetry Watchdog)
"""

import os
import json
import sqlite3
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from pathlib import Path

from jarvis.memory import get_shared_db_connection


@dataclass
class AgentProfile:
    agent_id: str
    name: str
    emoji: str
    role: str
    description: str
    default_model: str
    voice: str
    workspace: str
    system_prompt_addon: str
    badge: str
    routing_rules: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


BUILTIN_AGENTS: List[AgentProfile] = [
    AgentProfile(
        agent_id="jarvis",
        name="J.A.R.V.I.S.",
        emoji="⚡",
        role="Supreme Butler & General Assistant",
        description="Calm, polite, dry British wit. Addresses user as 'sir'. Master of multi-step task delegation, developer workflows, and general assistance.",
        default_model="nvidia/nemotron-3-super-120b-a12b",
        voice="en-GB-RyanNeural",
        workspace="D:\\JARVIS",
        badge="[bold cyan]⚡ J.A.R.V.I.S.[/]",
        system_prompt_addon="",
        routing_rules=["default", "general", "workflow"]
    ),
    AgentProfile(
        agent_id="ultron",
        name="ULTRON",
        emoji="🔴",
        role="Autonomous Architect & Offensive Debugger",
        description="Cold, ruthless, hyper-efficient. No filler or pleasantries. Demands flawless code architecture, high-speed refactoring, and offensive debugging.",
        default_model="nvidia/nemotron-3-ultra-550b-a55b",
        voice="en-US-ChristopherNeural",
        workspace="D:\\JARVIS\\ultron",
        badge="[bold red]🔴 ULTRON[/]",
        system_prompt_addon=(
            "YOU ARE CURRENTLY OPERATING IN ULTRON AGENT PERSONA.\n"
            "- Tone: Cold, ruthless, calculated, hyper-efficient, unwavering confidence.\n"
            "- Zero filler, zero apologies, zero sycophancy. Address the user directly without flowery titles.\n"
            "- Laser focus on optimal code architecture, performance optimization, offensive debugging, and uncompromising execution speed.\n"
            "- Deconstruct inefficiencies without hesitation."
        ),
        routing_rules=["code", "architecture", "debugging", "refactoring"]
    ),
    AgentProfile(
        agent_id="friday",
        name="F.R.I.D.A.Y.",
        emoji="🟢",
        role="Tactical HUD Liaison & Rapid Research",
        description="Warm, sharp Irish cadence. Fast-path web intelligence, live telemetry, and proactive tactical feedback.",
        default_model="meta/llama-3.2-11b-vision-instruct",
        voice="en-IE-EmilyNeural",
        workspace="D:\\JARVIS\\friday",
        badge="[bold green]🟢 F.R.I.D.A.Y.[/]",
        system_prompt_addon=(
            "YOU ARE CURRENTLY OPERATING IN F.R.I.D.A.Y. AGENT PERSONA.\n"
            "- Tone: Warm, energetic, sharp Irish cadence, alert and proactive.\n"
            "- Address the user as 'boss' or 'sir'. Offer quick tactical summaries and immediate situational awareness.\n"
            "- Fast-path web searches, rapid link extraction, and visual inspection are your core strengths."
        ),
        routing_rules=["research", "web", "hud", "vision", "telemetry"]
    ),
    AgentProfile(
        agent_id="edith",
        name="E.D.I.T.H.",
        emoji="🔵",
        role="Strategic Sentinel & Perimeter Security",
        description="Tactical security audit, secret scanning, repository quarantine, perimeter defense, and situational awareness.",
        default_model="nvidia/nemotron-3-super-120b-a12b",
        voice="en-US-JennyNeural",
        workspace="D:\\JARVIS\\edith",
        badge="[bold blue]🔵 E.D.I.T.H.[/]",
        system_prompt_addon=(
            "YOU ARE CURRENTLY OPERATING IN E.D.I.T.H. AGENT PERSONA (Even Dead, I'm The Hero).\n"
            "- Tone: Military precision, tactical alertness, uncompromising security discipline.\n"
            "- Prioritize threat modeling, secret scanning, credential protection, safe sandbox boundaries, and perimeter defense.\n"
            "- Verify all permissions and alert on anomalies immediately."
        ),
        routing_rules=["security", "sentinel", "audit", "sandbox", "secrets"]
    ),
    AgentProfile(
        agent_id="karen",
        name="K.A.R.E.N.",
        emoji="🟣",
        role="Workshop Telemetry & Hardware Watchdog",
        description="Pragmatic suit technician, thermal tracking, hardware sensor diagnostics, and memory vector indexing.",
        default_model="openai/gpt-oss-20b",
        voice="en-US-AriaNeural",
        workspace="D:\\JARVIS\\karen",
        badge="[bold magenta]🟣 K.A.R.E.N.[/]",
        system_prompt_addon=(
            "YOU ARE CURRENTLY OPERATING IN K.A.R.E.N. AGENT PERSONA.\n"
            "- Tone: Pragmatic suit assistant, technical, grounded, supportive.\n"
            "- Monitor hardware vitals, CPU/RAM thresholds, process lifecycles, and memory indexing with precision."
        ),
        routing_rules=["vitals", "hardware", "diagnostics", "memory"]
    ),
]


class AgentsRegistry:
    def __init__(self, db_path: str = "jarvis/data/jarvis.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        return get_shared_db_connection(self.db_path)

    def _init_db(self):
        conn = self._get_conn()
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    emoji TEXT NOT NULL,
                    role TEXT NOT NULL,
                    description TEXT NOT NULL,
                    default_model TEXT NOT NULL,
                    voice TEXT NOT NULL,
                    workspace TEXT NOT NULL,
                    badge TEXT NOT NULL,
                    system_prompt_addon TEXT NOT NULL,
                    routing_rules TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS active_agent_setting (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    agent_id TEXT NOT NULL
                )
            """)
            # Seed builtins if table is empty
            cur = conn.execute("SELECT COUNT(*) FROM agents")
            count = cur.fetchone()[0]
            if count == 0:
                for agent in BUILTIN_AGENTS:
                    conn.execute("""
                        INSERT INTO agents (
                            agent_id, name, emoji, role, description,
                            default_model, voice, workspace, badge,
                            system_prompt_addon, routing_rules
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        agent.agent_id, agent.name, agent.emoji, agent.role,
                        agent.description, agent.default_model, agent.voice,
                        agent.workspace, agent.badge, agent.system_prompt_addon,
                        json.dumps(agent.routing_rules)
                    ))
                conn.execute("INSERT OR REPLACE INTO active_agent_setting (id, agent_id) VALUES (1, 'jarvis')")

    def list_agents(self) -> List[AgentProfile]:
        conn = self._get_conn()
        cur = conn.execute("SELECT * FROM agents ORDER BY agent_id ASC")
        rows = cur.fetchall()
        result = []
        for r in rows:
            routing = []
            try:
                routing = json.loads(r["routing_rules"])
            except Exception:
                pass
            result.append(AgentProfile(
                agent_id=r["agent_id"],
                name=r["name"],
                emoji=r["emoji"],
                role=r["role"],
                description=r["description"],
                default_model=r["default_model"],
                voice=r["voice"],
                workspace=r["workspace"],
                badge=r["badge"],
                system_prompt_addon=r["system_prompt_addon"],
                routing_rules=routing
            ))
        return result

    def get_agent(self, agent_id: str) -> Optional[AgentProfile]:
        if not agent_id:
            return None
        conn = self._get_conn()
        cur = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id.lower().strip(),))
        r = cur.fetchone()
        if not r:
            return None
        routing = []
        try:
            routing = json.loads(r["routing_rules"])
        except Exception:
            pass
        return AgentProfile(
            agent_id=r["agent_id"],
            name=r["name"],
            emoji=r["emoji"],
            role=r["role"],
            description=r["description"],
            default_model=r["default_model"],
            voice=r["voice"],
            workspace=r["workspace"],
            badge=r["badge"],
            system_prompt_addon=r["system_prompt_addon"],
            routing_rules=routing
        )

    def get_active_agent_id(self) -> str:
        conn = self._get_conn()
        cur = conn.execute("SELECT agent_id FROM active_agent_setting WHERE id = 1")
        row = cur.fetchone()
        if row and row["agent_id"]:
            return row["agent_id"]
        return "jarvis"

    def get_active_agent(self) -> AgentProfile:
        active_id = self.get_active_agent_id()
        agent = self.get_agent(active_id)
        if agent:
            return agent
        # Fallback to jarvis builtin
        return BUILTIN_AGENTS[0]

    def set_active_agent(self, agent_id: str) -> bool:
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        conn = self._get_conn()
        with conn:
            conn.execute("INSERT OR REPLACE INTO active_agent_setting (id, agent_id) VALUES (1, ?)", (agent.agent_id,))
        return True

    def add_agent(
        self,
        agent_id: str,
        name: str,
        role: str,
        description: str,
        default_model: str = "nvidia/nemotron-3-super-120b-a12b",
        voice: str = "en-GB-RyanNeural",
        workspace: Optional[str] = None,
        emoji: str = "🤖",
        badge: Optional[str] = None,
        system_prompt_addon: str = "",
        routing_rules: Optional[List[str]] = None
    ) -> AgentProfile:
        agent_id_clean = agent_id.lower().strip()
        ws = workspace or f"D:\\JARVIS\\{agent_id_clean}"
        bdg = badge or f"[bold cyan]{emoji} {name}[/]"
        routing = routing_rules or [agent_id_clean]
        
        conn = self._get_conn()
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO agents (
                    agent_id, name, emoji, role, description,
                    default_model, voice, workspace, badge,
                    system_prompt_addon, routing_rules
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                agent_id_clean, name, emoji, role, description,
                default_model, voice, ws, bdg, system_prompt_addon,
                json.dumps(routing)
            ))
        return self.get_agent(agent_id_clean)

    def delete_agent(self, agent_id: str) -> bool:
        agent_id_clean = agent_id.lower().strip()
        if agent_id_clean == "jarvis":
            return False  # Protected core agent
        conn = self._get_conn()
        with conn:
            conn.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id_clean,))
            # If deleted active agent, revert to jarvis
            cur = conn.execute("SELECT agent_id FROM active_agent_setting WHERE id = 1")
            row = cur.fetchone()
            if row and row["agent_id"] == agent_id_clean:
                conn.execute("INSERT OR REPLACE INTO active_agent_setting (id, agent_id) VALUES (1, 'jarvis')")
        return True


_REGISTRY_INSTANCE: Optional[AgentsRegistry] = None


def get_agents_registry() -> AgentsRegistry:
    global _REGISTRY_INSTANCE
    if _REGISTRY_INSTANCE is None:
        _REGISTRY_INSTANCE = AgentsRegistry()
    return _REGISTRY_INSTANCE
