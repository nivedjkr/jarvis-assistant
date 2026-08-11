import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
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

app = FastAPI()

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8765",
    "http://127.0.0.1:8765",
    "vscode-webview://*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

WS_AUTH_TOKEN = os.getenv("JARVIS_WS_TOKEN", "jarvis_secure_local_token_2026")

# Shared instances
api_client = JarvisAPIClient()
tool_registry = ToolRegistry()
tts_engine = TTSEngine()  # Single shared TTS engine

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

    session_id = f"electron_{uuid.uuid4().hex[:8]}"
    
    # Run startup health check and send report to desktop client
    report = await run_diagnostics(check_nvidia=True)
    await ws.send_json({
        "type": "status",
        "status": "connected",
        "message": "JARVIS online, sir.",
        "health_check": report.to_dict()
    })
    
    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "message")
            
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
                    elif cmd.startswith("/provider"):
                        from jarvis.llm_provider import get_provider
                        parts = user_msg.strip().split(maxsplit=1)
                        prov_name = parts[1] if len(parts) > 1 else ""
                        if prov_name:
                            api_client.provider = get_provider(prov_name)
                            api_client.model = getattr(api_client.provider, 'model', 'default')
                            res = f"LLM Provider switched to: {api_client.provider.name}"
                        else:
                            res = f"Active Provider: {getattr(api_client.provider, 'name', 'NVIDIA NIM')}"
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

                        api_client.add_user_message(user_msg, session_id=session_id)
                        response = await api_client.chat_with_tools(
                            tool_schemas=tool_registry.schemas,
                            tool_executor=tracking_executor,
                            session_id=session_id
                        )
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

                    api_client.add_user_message(user_msg, session_id=session_id)
                    response = await api_client.chat_with_tools(
                        tool_schemas=tool_registry.schemas,
                        tool_executor=tracking_executor,
                        session_id=session_id
                    )
                    
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

                    # Send response back to Electron
                    await ws.send_json({
                        "type": "response",
                        "text": response,
                        "tool_calls": executed_tools,
                        "status": "speaking"
                    })
                    
                    print(f"[WS] Sent response ({len(executed_tools)} tools executed): {response[:100]}")
                    
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
        session_id=session_id
    )
    
    # Push to all connected WebSocket clients
    await manager.broadcast({
        "type": "proactive_alert",
        "text": f"[{source}] {response}",
        "alert_type": "api"
    })
    
    return {"response": response}

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
    try:
        from jarvis.projects import get_projects_summary
        return get_projects_summary()
    except Exception:
        return []

@app.get("/reminders")
async def reminders_endpoint():
    return []

@app.get("/watchlist")
async def watchlist_endpoint():
    return []

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

if __name__ == "__main__":
    print("[API] Starting JARVIS WebSocket server...")
    print("[API] Running startup health check...")
    report = run_diagnostics_sync(check_nvidia=True)
    print(report.format_plain())
    print("[API] Electron can connect at ws://127.0.0.1:8765/ws")
    try:
        uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
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