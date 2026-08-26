import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import asyncio
import json
import sys
from pathlib import Path
from typing import Set

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from jarvis.api_client import JarvisAPIClient
from jarvis.tools import ToolRegistry
from jarvis.voice import TTSEngine
from jarvis.diagnostics import run_diagnostics, run_diagnostics_sync
from jarvis.proactive_engine import ProactiveFollowUpEngine

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    if hasattr(api_client, 'semantic_memory') and api_client.semantic_memory:
        asyncio.create_task(asyncio.to_thread(api_client.semantic_memory.prewarm))
    yield

app = FastAPI(lifespan=lifespan)

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8765",
    "http://127.0.0.1:8765",
    "vscode-webview://*"
]

custom_origins = os.getenv("JARVIS_ALLOWED_ORIGINS", "")
if custom_origins:
    for origin in custom_origins.split(","):
        origin_clean = origin.strip()
        if origin_clean and origin_clean != "*" and origin_clean not in ALLOWED_ORIGINS:
            ALLOWED_ORIGINS.append(origin_clean)

ALLOW_ORIGIN_REGEX = r"https?://(localhost|127\.0\.0\.1|100\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}|[a-zA-Z0-9\.\-]+\.ts\.net)(:\d+)?"

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

WS_AUTH_TOKEN = os.getenv("JARVIS_WS_TOKEN", "jarvis_secure_local_token_2026")

@app.get("/mobile/config.json")
async def mobile_config_endpoint():
    return {
        "ws_token": WS_AUTH_TOKEN,
        "status": "online"
    }

mobile_dir = Path(__file__).parent.parent / "jarvis-mobile"
if mobile_dir.exists():
    try:
        cfg_file = mobile_dir / "config.json"
        cfg_file.write_text(json.dumps({"ws_token": WS_AUTH_TOKEN, "status": "online"}), encoding="utf-8")
    except Exception:
        pass
    app.mount("/mobile", StaticFiles(directory=str(mobile_dir), html=True), name="mobile")

api_client = JarvisAPIClient()
tool_registry = ToolRegistry()
tts_engine = TTSEngine()
proactive_engine = ProactiveFollowUpEngine()


def handle_tool_state_change(domain: str, action: str, payload: dict):
    from datetime import datetime
    msg = {
        "type": "state_update",
        "domain": domain,
        "action": action,
        "payload": payload,
        "timestamp": datetime.now().isoformat()
    }
    print(f"[WS] Broadcasting state update ({domain} -> {action})")
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast(msg))
    except Exception:
        pass

tool_registry.on_state_change = handle_tool_state_change

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"[WS] Client connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        print(f"[WS] Client disconnected. Total: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception:
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

import uuid

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    # Verify auth token from query params or headers
    token = ws.query_params.get("token") or ws.headers.get("x-auth-token")
    if not token or token != WS_AUTH_TOKEN:
        # Check for auth handshake message
        await ws.accept()
        try:
            auth_data = await asyncio.wait_for(ws.receive_json(), timeout=2.0)
            if auth_data.get("type") == "auth" and auth_data.get("token") == WS_AUTH_TOKEN:
                token = WS_AUTH_TOKEN
            else:
                await ws.send_json({"type": "error", "message": "Authentication failed: Invalid token"})
                await ws.close(code=1008)
                return
        except Exception:
            await ws.send_json({"type": "error", "message": "Authentication failed: Auth handshake required"})
            await ws.close(code=1008)
            return
    else:
        await manager.connect(ws)

    req_session_id = ws.query_params.get("session_id")
    if req_session_id and req_session_id.strip():
        session_id = req_session_id.strip()
    else:
        session_id = f"electron_{uuid.uuid4().hex[:8]}"
    
    active_sess = api_client.get_session(session_id)
    
    try:
        # Run startup health check and send report to desktop/mobile client
        report = await run_diagnostics(check_nvidia=True)
        initial_msgs = [{"role": m["role"], "content": m["content"]} for m in active_sess.messages]
        await ws.send_json({
            "type": "status",
            "status": "connected",
            "message": "JARVIS online, sir.",
            "session_id": session_id,
            "session_title": active_sess.title,
            "messages": initial_msgs,
            "health_check": report.to_dict()
        })
        
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "get_sessions" or msg_type == "list_sessions":
                sessions = api_client.list_sessions()
                await ws.send_json({
                    "type": "sessions_list",
                    "sessions": sessions,
                    "current_session_id": session_id
                })
                continue

            if msg_type == "switch_session":
                target_sid = data.get("session_id", "").strip()
                if target_sid:
                    session_id = target_sid
                    sess = api_client.get_session(session_id)
                    msgs = [{"role": m["role"], "content": m["content"]} for m in sess.messages]
                    await ws.send_json({
                        "type": "session_switched",
                        "session_id": session_id,
                        "title": sess.title,
                        "messages": msgs
                    })
                continue

            if msg_type == "new_session":
                title = data.get("title", "New Conversation")
                new_sess = api_client.new_session(title=title)
                session_id = new_sess.session_id
                await ws.send_json({
                    "type": "session_created",
                    "session_id": session_id,
                    "title": new_sess.title,
                    "messages": []
                })
                continue

            if msg_type == "rename_session":
                target_sid = data.get("session_id", session_id)
                new_title = data.get("title", "").strip()
                if target_sid and new_title:
                    api_client.rename_session(target_sid, new_title)
                    sessions = api_client.list_sessions()
                    await ws.send_json({
                        "type": "sessions_list",
                        "sessions": sessions,
                        "current_session_id": session_id
                    })
                continue

            if msg_type == "get_missions" or msg_type == "list_missions":
                missions = proactive_engine.mission_manager.list_missions()
                await ws.send_json({
                    "type": "missions_list",
                    "missions": [m.to_dict() for m in missions]
                })
                continue

            if msg_type == "get_mission":
                mid = data.get("mission_id", "").strip()
                m = proactive_engine.mission_manager.get_mission(mid)
                await ws.send_json({
                    "type": "mission_details",
                    "mission": m.to_dict() if m else None
                })
                continue

            if msg_type == "mission_action":
                action = data.get("action", "").lower().strip()
                mid = data.get("mission_id", "").strip()
                res_text = "Mission action completed."
                try:
                    if action == "pause":
                        m = proactive_engine.mission_manager.pause_mission(mid)
                        res_text = f"Paused mission '{m.title}', sir."
                    elif action == "resume":
                        m = proactive_engine.mission_manager.resume_mission(mid)
                        res_text = f"Resumed mission '{m.title}', sir."
                    elif action == "cancel":
                        m = proactive_engine.mission_manager.cancel_mission(mid)
                        res_text = f"Cancelled mission '{m.title}', sir."
                    elif action == "approve":
                        m = proactive_engine.mission_manager.approve_mission(mid)
                        res_text = f"Approved and activated mission '{m.title}', sir."
                except Exception as me:
                    res_text = f"Mission error: {me}"

                await ws.send_json({
                    "type": "response",
                    "text": res_text,
                    "status": "speaking"
                })
                continue

            if msg_type == "delete_session":

                target_sid = data.get("session_id", "").strip()
                if target_sid:
                    api_client.delete_session(target_sid)
                    sessions = api_client.list_sessions()
                    await ws.send_json({
                        "type": "sessions_list",
                        "sessions": sessions,
                        "current_session_id": session_id
                    })
                continue
            
            if msg_type == "confirm_action":
                act_id = data.get("action_id", "")
                extra = data.get("input", "") or data.get("extra_input", "")
                res = tool_registry.confirm_action(act_id, extra)
                await ws.send_json({
                    "type": "response",
                    "text": res,
                    "status": "speaking"
                })
                continue
            
            if msg_type == "message" or msg_type == "slash_command":
                user_msg = data.get("message") or data.get("command") or ""
                user_msg = user_msg.strip()
                print(f"[WS] Received ({msg_type}): {user_msg}")
                
                if not user_msg:
                    continue
                
                # Send thinking status
                await ws.send_json({
                    "type": "status",
                    "status": "thinking"
                })
                
                # Check slash command handling
                if user_msg.startswith("/"):
                    cmd = user_msg.lower()
                    if user_msg.lower().startswith("/confirm"):
                        parts = user_msg.strip().split(maxsplit=2)
                        act_id = parts[1] if len(parts) > 1 else ""
                        extra = parts[2] if len(parts) > 2 else ""
                        res = tool_registry.confirm_action(act_id, extra)
                        await ws.send_json({
                            "type": "response",
                            "text": res,
                            "status": "speaking"
                        })
                    elif cmd == "/diagnose":
                        from jarvis.health import HealthChecker
                        checker = HealthChecker()
                        await checker.run_all()
                        res_text = checker.render_results()
                        await ws.send_json({
                            "type": "response",
                            "text": res_text,
                            "status": "idle"
                        })
                    elif cmd.startswith("/debug"):
                        from jarvis.debug_panel import debug
                        parts = user_msg.strip().split()
                        sub = parts[1].lower() if len(parts) > 1 else ""
                        if sub == "on":
                            debug.enabled = True
                            res = "Debug panel enabled, sir."
                        elif sub == "off":
                            debug.enabled = False
                            res = "Debug panel disabled, sir."
                        else:
                            res = debug.render()
                        await ws.send_json({
                            "type": "response",
                            "text": res,
                            "status": "speaking"
                        })
                    elif cmd.startswith("/missions") or cmd.startswith("/mission"):
                        parts = user_msg.strip().split(maxsplit=2)
                        subcmd = parts[0].lower()
                        arg1 = parts[1].lower() if len(parts) > 1 else ""
                        arg2 = parts[2] if len(parts) > 2 else ""

                        if subcmd == "/missions" or not arg1:
                            missions = proactive_engine.mission_manager.list_missions()
                            if not missions:
                                res = "No active or proposed missions found, sir."
                            else:
                                lines = [f"• [{m.id}] {m.title} ({m.status.value}) - Progress: {m.progress_percentage}% ({m.completed_task_count}/{m.task_count} tasks)" for m in missions]
                                res = "=== ACTIVE & PROPOSED MISSIONS ===\n" + "\n".join(lines)
                        elif arg1 == "pause" and arg2:
                            try:
                                m = proactive_engine.mission_manager.pause_mission(arg2)
                                res = f"Paused mission '{m.title}' [{m.id}], sir."
                            except Exception as me:
                                res = f"Error pausing mission: {me}"
                        elif arg1 == "resume" and arg2:
                            try:
                                m = proactive_engine.mission_manager.resume_mission(arg2)
                                res = f"Resumed mission '{m.title}' [{m.id}], sir."
                            except Exception as me:
                                res = f"Error resuming mission: {me}"
                        elif arg1 == "cancel" and arg2:
                            try:
                                m = proactive_engine.mission_manager.cancel_mission(arg2)
                                res = f"Cancelled mission '{m.title}' [{m.id}], sir."
                            except Exception as me:
                                res = f"Error cancelling mission: {me}"
                        elif arg1 in ("approve", "confirm") and arg2:
                            try:
                                m = proactive_engine.mission_manager.approve_mission(arg2)
                                res = f"Approved and activated mission '{m.title}' [{m.id}], sir. Created {m.task_count} initial tasks."
                            except Exception as me:
                                res = f"Error approving mission: {me}"
                        else:
                            # Assume arg1 is mission ID
                            m = proactive_engine.mission_manager.get_mission(arg1)
                            if not m:
                                res = f"Mission '{arg1}' not found, sir."
                            else:
                                task_lines = [f"  [{t.id}] {t.title} ({t.status.value})" for t in m.tasks]
                                res = (
                                    f"Mission: {m.title} [{m.id}]\n"
                                    f"Status: {m.status.value} | Progress: {m.progress_percentage}%\n"
                                    f"Objective: {m.objective}\n"
                                    f"Tasks ({len(m.tasks)}):\n" + ("\n".join(task_lines) if task_lines else "  No tasks created yet.")
                                )

                        await ws.send_json({
                            "type": "response",
                            "text": res,
                            "status": "speaking"
                        })
                    elif cmd.startswith("/provider"):

                        from jarvis.llm_provider import get_provider
                        from jarvis.error_recovery import recovery
                        parts = user_msg.strip().split(maxsplit=1)
                        prov_name = parts[1].strip() if len(parts) > 1 else ""
                        if prov_name.lower() == "reset":
                            recovery.reset_circuit()
                            api_client.provider = get_provider()
                            api_client.model = getattr(api_client.provider, 'model', 'default')
                            res = f"Reset all LLM circuit breakers. Active provider: {api_client.provider.name}"
                        elif prov_name:
                            api_client.provider = get_provider(prov_name)
                            api_client.model = getattr(api_client.provider, 'model', 'default')
                            res = f"LLM Provider switched to: {api_client.provider.name}"
                        else:
                            cb_status = recovery.circuit_breakers
                            open_cbs = [k for k, v in cb_status.items() if v.get('open')]
                            open_msg = f" (Circuit open: {', '.join(open_cbs)})" if open_cbs else " (Circuits operational)"
                            res = f"Active Provider: {getattr(api_client.provider, 'name', 'NVIDIA NIM')}{open_msg}. Use '/provider reset' to clear circuit breakers."
                        await ws.send_json({
                            "type": "response",
                            "text": res,
                            "status": "speaking"
                        })
                    elif cmd.startswith("/config"):
                        from jarvis.config_manager import config
                        parts = user_msg.strip().split(maxsplit=2)
                        sub = parts[1].lower() if len(parts) > 1 else "show"
                        if sub == "show":
                            import yaml
                            res = "=== JARVIS CONFIGURATION ===\n" + yaml.dump(config.get_all(), default_flow_style=False)
                        elif sub == "set" and len(parts) > 2:
                            kv = parts[2].split(maxsplit=1)
                            if len(kv) == 2:
                                config.set(kv[0], kv[1])
                                res = f"Set config path '{kv[0]}' to '{kv[1]}'."
                            else:
                                res = "Usage: /config set <path> <value>"
                        elif sub == "save":
                            config.save()
                            res = "Configuration saved to config.yaml."
                        elif sub == "reset":
                            config.reload()
                            res = "Configuration reloaded from config.yaml."
                        else:
                            res = "Usage: /config [show|set <path> <val>|save|reset]"
                        await ws.send_json({
                            "type": "response",
                            "text": res,
                            "status": "speaking"
                        })
                    elif cmd.startswith("/memory"):
                        from jarvis.memory import list_all_facts, delete_fact, edit_fact, clear_facts_by_category, get_memory_stats, search_facts, export_memory
                        parts = user_msg.strip().split(maxsplit=2)
                        sub = parts[1].lower() if len(parts) > 1 else "stats"
                        if sub == "stats":
                            st = get_memory_stats()
                            res = f"Total Facts: {st['total_facts']}\nBy Category: {st['by_category']}"
                        elif sub == "list":
                            cat = parts[2] if len(parts) > 2 else None
                            facts = list_all_facts(category=cat, limit=20)
                            if not facts:
                                res = "No facts found."
                            else:
                                lines = [f"#{f['id']} [{f.get('category','gen')}] {f.get('content','')[:60]}" for f in facts]
                                res = "Memory Facts:\n" + "\n".join(lines)
                        elif sub == "delete" and len(parts) > 2:
                            try:
                                fid = int(parts[2])
                                res = delete_fact(fid)
                            except ValueError:
                                res = "Invalid fact ID."
                        elif sub == "edit" and len(parts) > 2:
                            try:
                                edit_parts = parts[2].split(maxsplit=1)
                                fid = int(edit_parts[0])
                                n_content = edit_parts[1] if len(edit_parts) > 1 else ""
                                res = edit_fact(fid, n_content)
                            except ValueError:
                                res = "Usage: /memory edit <id> <new content>"
                        elif sub == "clear" and len(parts) > 2:
                            res = clear_facts_by_category(parts[2])
                        elif sub == "search" and len(parts) > 2:
                            facts = search_facts(parts[2])
                            lines = [f"#{f['id']} [{f.get('category','gen')}] {f.get('content','')[:60]}" for f in facts]
                            res = f"Search Results ({len(facts)}):\n" + "\n".join(lines) if lines else "No matching facts."
                        elif sub == "export":
                            res = export_memory()
                        else:
                            res = "Usage: /memory [stats|list|delete <id>|edit <id> <content>|clear <cat>|search <kw>|export]"
                        await ws.send_json({
                            "type": "response",
                            "text": res,
                            "status": "speaking"
                        })
                    elif cmd in ["/google auth", "/google login", "/email auth", "/calendar auth", "/google_auth", "/auth google"]:
                        await ws.send_json({
                            "type": "response",
                            "text": "Opening Google OAuth authorization in your web browser, sir. Please complete the login prompt.",
                            "status": "speaking"
                        })
                        res = await tool_registry.execute("authenticate_google", {})
                        await ws.send_json({
                            "type": "response",
                            "text": res,
                            "tool_calls": [{"name": "authenticate_google"}],
                            "status": "speaking"
                        })
                    elif cmd in ["/email", "/check_email", "/checkemail"]:
                        res = await tool_registry.execute("check_email", {"limit": 5})
                        await ws.send_json({
                            "type": "response",
                            "text": res,
                            "tool_calls": [{"name": "check_email"}],
                            "status": "speaking"
                        })
                    elif cmd in ["/email summary", "/email_summary", "/email-summary"]:
                        res = await tool_registry.execute("email_summary", {})
                        await ws.send_json({
                            "type": "response",
                            "text": res,
                            "tool_calls": [{"name": "email_summary"}],
                            "status": "speaking"
                        })
                    elif cmd == "/tools":
                        tools_list = list(tool_registry.tools.keys())
                        await ws.send_json({
                            "type": "response",
                            "text": f"Registered Tools ({len(tools_list)}):\n" + ", ".join(tools_list),
                            "status": "speaking"
                        })
                    elif cmd == "/help":
                        help_text = (
                            "=====================================================\n"
                            "            J.A.R.V.I.S. SYSTEM COMMAND REFERENCE    \n"
                            "=====================================================\n\n"
                            "--- SLASH COMMANDS ---\n"
                            "  /help          Show this command reference\n"
                            "  /tools         List all 59 registered tool schemas\n"
                            "  /email         Check recent unread emails in Gmail\n"
                            "  /email summary Get executive email briefing\n"
                            "  /diagnose      Run system diagnostics & health check\n"
                            "  /context       View active session token usage\n"
                            "  /context clear Reset session context memory\n"
                            "  /exit          Disconnect active session\n\n"
                            "--- GMAIL & EMAIL COMMANDS ---\n"
                            "  • 'check my email' / '/email'\n"
                            "  • 'email summary' / '/email summary'\n"
                            "  • 'read email 1' (reads body of email #1)\n"
                            "  • 'send email to name@domain.com subject Title body Message'\n"
                            "  • 'confirm' / 'yes' (confirms draft send)\n\n"
                            "--- SYSTEM & UTILITIES ---\n"
                            "  • 'what is my cpu usage?'\n"
                            "  • 'get disk usage'\n"
                            "  • 'open spotify' / 'close notepad'\n"
                            "  • 'copy hello world to clipboard'\n\n"
                            "--- DEVELOPER & GITHUB ---\n"
                            "  • 'git status' / 'git log'\n"
                            "  • 'show my github repos'\n"
                            "  • 'list open pull requests'\n\n"
                            "====================================================="
                        )
                        await ws.send_json({
                            "type": "response",
                            "text": help_text,
                            "status": "speaking"
                        })
                    elif cmd == "/context":
                        msgs = api_client.get_session(session_id).messages
                        tokens = api_client.get_token_estimate(session_id)
                        await ws.send_json({
                            "type": "response",
                            "text": f"Session Context: {len(msgs)} messages, ~{tokens} estimated tokens.",
                            "status": "speaking"
                        })
                    elif cmd == "/context clear":
                        api_client.clear_history(session_id)
                        await ws.send_json({
                            "type": "response",
                            "text": "Context history cleared, sir.",
                            "status": "speaking"
                        })
                    elif cmd == "/exit":
                        await ws.send_json({
                            "type": "response",
                            "text": "Goodbye, sir.",
                            "status": "idle"
                        })
                    else:
                        # Fallback slash command or natural query starting with /
                        executed_tools = []
                        async def tracking_executor(name: str, args: dict) -> str:
                            executed_tools.append({"name": name, "args": args})
                            return await tool_registry.execute(name, args)

                        async def send_chunk(chunk_text: str):
                            try:
                                await ws.send_json({"type": "chunk", "text": chunk_text})
                            except Exception:
                                pass

                        try:
                            api_client.add_user_message(user_msg, session_id=session_id)
                            response = await api_client.chat_with_tools(
                                tool_schemas=tool_registry.schemas,
                                tool_executor=tracking_executor,
                                session_id=session_id,
                                tool_registry=tool_registry,
                                chunk_callback=send_chunk
                            )
                        except Exception as err:
                            print(f"[API ERROR] Error processing slash command/query: {err}")
                            response = f"I encountered an error processing your request, sir: {err}"

                        await ws.send_json({
                            "type": "response",
                            "text": response,
                            "tool_calls": executed_tools,
                            "status": "speaking"
                        })
                else:
                    # Check if there are pending actions awaiting confirmation and user typed an affirmative / confirmation response
                    if tool_registry.pending_actions:
                        import re
                        lower_m = user_msg.lower().strip()
                        confirm_words = ["confirm", "yes", "yep", "yeah", "proceed", "approve", "do it", "send", "send it", "ok", "okay", "go ahead"]
                        act_match = re.search(r'act_[a-f0-9]+', lower_m)
                        
                        if act_match or any(lower_m == w or lower_m.startswith(w + " ") or lower_m.endswith(" " + w) for w in confirm_words):
                            act_id = act_match.group(0) if act_match else ""
                            extra = user_msg.split(maxsplit=1)[1] if " " in user_msg and not act_match else user_msg
                            res = tool_registry.confirm_action(act_id, extra)
                            await ws.send_json({
                                "type": "response",
                                "text": res,
                                "status": "speaking"
                            })
                            continue

                    # Natural language prompt processing with tool tracking
                    executed_tools = []
                    async def tracking_executor(name: str, args: dict) -> str:
                        executed_tools.append({"name": name, "args": args})
                        return await tool_registry.execute(name, args)

                    async def send_chunk(chunk_text: str):
                        try:
                            await ws.send_json({"type": "chunk", "text": chunk_text})
                        except Exception:
                            pass

                    try:
                        api_client.add_user_message(user_msg, session_id=session_id)
                        response = await api_client.chat_with_tools(
                            tool_schemas=tool_registry.schemas,
                            tool_executor=tracking_executor,
                            session_id=session_id,
                            tool_registry=tool_registry,
                            chunk_callback=send_chunk
                        )
                    except Exception as err:
                        print(f"[API ERROR] Error processing message: {err}")
                        response = f"I encountered an error processing your request, sir: {err}"
                    
                    # Intent fallback safety: ONLY trigger if user explicitly issued a direct command to check email and LLM produced no tool calls
                    if not executed_tools:
                        lower_msg = user_msg.lower().strip()
                        negatives_or_questions = ["don't", "dont", "do not", "never", "stop", "no ", "not ", "how ", "what ", "why ", "explain ", "tell me", "can you"]
                        if not any(neg in lower_msg for neg in negatives_or_questions):
                            EXPLICIT_CHECK_COMMANDS = [
                                "check email", "check my email", "check inbox", "check my inbox",
                                "check gmail", "check my gmail", "read email", "read my email",
                                "show email", "show my email", "show unread emails", "list emails",
                                "list my emails", "get emails", "get unread emails"
                            ]
                            if any(cmd == lower_msg or lower_msg.startswith(cmd) for cmd in EXPLICIT_CHECK_COMMANDS):
                                res = await tool_registry.execute("check_email", {"limit": 5})
                                executed_tools.append({"name": "check_email", "args": {"limit": 5}})
                                response = res
                            elif "email summary" in lower_msg or "summarize email" in lower_msg:
                                res = await tool_registry.execute("email_summary", {})
                                executed_tools.append({"name": "email_summary", "args": {}})
                                response = res

                    # Final Response Firewall Check
                    from jarvis.tool_normalizer import is_unresolved_tool_call
                    if is_unresolved_tool_call(response, registered_tools=tool_registry.tools):
                        print(f"[WS FIREWALL] Blocked unexecuted tool call JSON from WebSocket output!")
                        response = "I have processed your request, sir."

                    # Send response back to Electron / Web clients
                    await ws.send_json({
                        "type": "response",
                        "text": response,
                        "tool_calls": executed_tools,
                        "status": "speaking"
                    })
                    
                    print(f"[WS] Sent response ({len(executed_tools)} tools executed): {response[:100]}")

                    # Trigger non-blocking Mark 5 Proactive Follow-Up Engine
                    async def broadcast_proactive(event_payload: dict):
                        try:
                            if event_payload.get("type") == "proactive_followup":
                                p_text = event_payload.get("text", "")
                                p_sid = event_payload.get("session_id", session_id)
                                api_client.add_assistant_message(p_text, session_id=p_sid)
                                await manager.broadcast({
                                    "type": "response",
                                    "text": p_text,
                                    "proactive": True,
                                    "status": "speaking"
                                })
                            else:
                                await manager.broadcast(event_payload)
                        except Exception as pe:
                            print(f"[WS] Proactive broadcast error: {pe}")

                    asyncio.create_task(
                        proactive_engine.analyze_and_followup(
                            session_id=session_id,
                            user_prompt=user_msg,
                            main_response=response,
                            tool_registry=tool_registry,
                            llm_client=api_client,
                            event_callback=broadcast_proactive
                        )
                    )

                    
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception as e:
        print(f"[WS] Connection error: {e}")
        manager.disconnect(ws)

@app.get("/status")
async def status():
    return {
        "status": "online",
        "model": api_client.model,
        "tools": len(tool_registry.tools),
        "ws_connections": len(manager.active_connections)
    }

@app.get("/health")
async def health_endpoint():
    report = await run_diagnostics(check_nvidia=True)
    return report.to_dict()

@app.post("/chat")
async def chat_endpoint(request: dict):
    message = request.get("message", "")
    source = request.get("source", "api")
    request_id = uuid.uuid4().hex[:8]
    session_id = f"api_{request_id}"
    print(f"[HTTP] Chat from {source}: {message}")
    
    api_client.add_user_message(message, session_id=session_id)
    response = await api_client.chat_with_tools(
        tool_schemas=tool_registry.schemas,
        tool_executor=tool_registry.execute,
        session_id=session_id,
        tool_registry=tool_registry
    )
    
    # Push to all connected WebSocket clients
    await manager.broadcast({
        "type": "proactive_alert",
        "text": f"[{source}] {response}",
        "alert_type": "api"
    })
    
    return {"response": response}

@app.post("/google/auth")
async def google_auth_endpoint():
    res = await tool_registry.execute("authenticate_google", {})
    return {"status": "ok", "message": res}

@app.post("/tts")
async def tts_endpoint(request: dict):
    text = request.get("text", "")
    try:
        b64 = await tts_engine.synthesize_to_base64(text)
        return {"audio": b64}
    except Exception as e:
        print(f"[TTS] Error: {e}")
        return {"audio": ""}

@app.post("/tts_sentence")
async def tts_sentence_endpoint(request: dict):
    sentence = request.get("sentence", "")
    try:
        b64 = await tts_engine.synthesize_sentence(sentence)
        return {"audio": b64}
    except Exception as e:
        print(f"[TTS] Error: {e}")
        return {"audio": ""}

@app.get("/projects")
async def projects_endpoint():
    """Returns active upcoming projects from Obsidian areas and local repositories."""
    try:
        from jarvis.projects import get_projects_summary
        projects = get_projects_summary()
        if projects:
            return projects
    except Exception:
        pass
    
    projects_list = []
    try:
        vault_path = tool_registry.obsidian_client.vault_path if tool_registry.obsidian_client else None
        if vault_path:
            areas_dir = Path(vault_path) / "Memory" / "areas"
            if areas_dir.exists():
                for p in areas_dir.glob("*.md"):
                    projects_list.append({
                        "id": p.stem,
                        "name": p.stem.replace("_", " ").title(),
                        "path": str(p),
                        "status": "Active"
                    })
    except Exception:
        pass

    if not projects_list:
        projects_list = [
            {"id": "jarvis-core", "name": "JARVIS Assistant Mk 4.8", "status": "Active"},
            {"id": "obsidian-vault", "name": "Obsidian Memory System", "status": "Synced"}
        ]
    return projects_list

@app.get("/calendar/events")
@app.get("/reminders")
async def get_calendar_events_endpoint():
    """Fetch real Google Calendar events via CalendarService."""
    events_data = []
    try:
        if tool_registry.calendar_service:
            raw_events = tool_registry.calendar_service.fetch_upcoming_events(force_refresh=False)
            for ev in raw_events:
                events_data.append({
                    "id": ev.get("id"),
                    "title": ev.get("summary") or "Untitled Event",
                    "summary": ev.get("summary") or "Untitled Event",
                    "start": ev.get("start"),
                    "end": ev.get("end"),
                    "location": ev.get("location", ""),
                    "description": ev.get("description", "")
                })
    except Exception as e:
        print(f"[API] Error fetching calendar events: {e}")

    return events_data

@app.get("/vitals")
async def vitals_endpoint():
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        return {
            "cpu_usage": cpu,
            "ram_usage": ram.percent,
            "ram_used_mb": ram.used // (1024 * 1024),
            "ram_total_mb": ram.total // (1024 * 1024)
        }
    except Exception:
        return {}

@app.get("/sessions")
@app.get("/api/sessions")
async def get_sessions_endpoint():
    return api_client.list_sessions()

@app.post("/sessions/new")
@app.post("/api/sessions/new")
async def new_session_endpoint(request: dict = None):
    title = (request or {}).get("title", "New Conversation")
    sess = api_client.new_session(title=title)
    return {
        "session_id": sess.session_id,
        "title": sess.title,
        "created_at": sess.created_at,
        "last_active": sess.last_active
    }

@app.get("/sessions/{session_id}/messages")
@app.get("/api/sessions/{session_id}/messages")
async def session_messages_endpoint(session_id: str):
    sess = api_client.get_session(session_id)
    return {
        "session_id": session_id,
        "title": sess.title,
        "messages": [{"role": m["role"], "content": m["content"]} for m in sess.messages]
    }

@app.post("/sessions/{session_id}/rename")
@app.post("/api/sessions/{session_id}/rename")
async def rename_session_endpoint(session_id: str, request: dict):
    title = (request or {}).get("title", "").strip()
    if not title:
        return {"status": "error", "message": "Title required"}
    success = api_client.rename_session(session_id, title)
    return {"status": "ok" if success else "error", "session_id": session_id, "title": title}

@app.delete("/sessions/{session_id}")
@app.post("/sessions/{session_id}/delete")
@app.delete("/api/sessions/{session_id}")
@app.post("/api/sessions/{session_id}/delete")
async def delete_session_endpoint(session_id: str):
    success = api_client.delete_session(session_id)
    return {"status": "ok" if success else "error", "session_id": session_id}

@app.get("/missions")
@app.get("/api/missions")
async def list_missions_endpoint(status: Optional[str] = None):
    m_status = None
    if status:
        try:
            from jarvis.mission_manager import MissionStatus
            m_status = MissionStatus(status.upper())
        except Exception:
            pass
    missions = proactive_engine.mission_manager.list_missions(status=m_status)
    return [m.to_dict() for m in missions]

@app.get("/missions/{mission_id}")
@app.get("/api/missions/{mission_id}")
async def get_mission_endpoint(mission_id: str):
    m = proactive_engine.mission_manager.get_mission(mission_id)
    if not m:
        return {"error": "Mission not found"}
    return m.to_dict()

@app.post("/missions/{mission_id}/pause")
@app.post("/api/missions/{mission_id}/pause")
async def pause_mission_endpoint(mission_id: str):
    try:
        m = proactive_engine.mission_manager.pause_mission(mission_id)
        return m.to_dict()
    except Exception as e:
        return {"error": str(e)}

@app.post("/missions/{mission_id}/resume")
@app.post("/api/missions/{mission_id}/resume")
async def resume_mission_endpoint(mission_id: str):
    try:
        m = proactive_engine.mission_manager.resume_mission(mission_id)
        return m.to_dict()
    except Exception as e:
        return {"error": str(e)}

@app.post("/missions/{mission_id}/cancel")
@app.post("/api/missions/{mission_id}/cancel")
async def cancel_mission_endpoint(mission_id: str):
    try:
        m = proactive_engine.mission_manager.cancel_mission(mission_id)
        return m.to_dict()
    except Exception as e:
        return {"error": str(e)}

@app.post("/missions/{mission_id}/approve")
@app.post("/api/missions/{mission_id}/approve")
async def approve_mission_endpoint(mission_id: str):
    try:
        m = proactive_engine.mission_manager.approve_mission(mission_id)
        return m.to_dict()
    except Exception as e:
        return {"error": str(e)}

def get_host_binding() -> str:

    allow_remote = os.getenv("JARVIS_ALLOW_REMOTE", "false").strip().lower() in ("true", "1", "yes")
    return "0.0.0.0" if allow_remote else "127.0.0.1"

if __name__ == "__main__":
    host = get_host_binding()
    print("[API] Starting JARVIS WebSocket server...")
    print("[API] Running startup health check...")
    report = run_diagnostics_sync(check_nvidia=True)
    print(report.format_plain())
    if host == "0.0.0.0":
        print("[API] Remote access ENABLED via JARVIS_ALLOW_REMOTE=true (listening on 0.0.0.0:8765)")
        print("[API] Tailscale / LAN connection active with JARVIS_WS_TOKEN auth required.")
    else:
        print("[API] Localhost-only mode (listening on 127.0.0.1:8765). Set JARVIS_ALLOW_REMOTE=true for LAN/Tailscale access.")
    print("[API] WebSocket clients can connect at ws://127.0.0.1:8765/ws")
    try:
        uvicorn.run(app, host=host, port=8765, log_level="info")
    except (OSError, Exception) as e:
        err_str = str(e)
        if "10048" in err_str or "98" in err_str or "address already in use" in err_str.lower():
            sys.stderr.write(
                "\n[API ERROR] Port 8765 already in use — a previous JARVIS backend process may still be running.\n"
            )
            sys.stderr.flush()
        else:
            sys.stderr.write(f"\n[API ERROR] Failed to start server: {e}\n")
            sys.stderr.flush()
        sys.exit(1)