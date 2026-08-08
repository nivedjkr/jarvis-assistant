from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Set

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from jarvis.api_client import JarvisAPIClient
from jarvis.tools import ToolRegistry
from jarvis.voice import TTSEngine

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

# Shared instances
api_client = JarvisAPIClient()
tool_registry = ToolRegistry()
tts_engine = TTSEngine()  # Single shared TTS engine

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
    session_id = f"electron_{uuid.uuid4().hex[:8]}"
    await manager.connect(ws)
    
    # Send connected confirmation
    await ws.send_json({
        "type": "status",
        "status": "connected",
        "message": "JARVIS online, sir."
    })
    
    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "message")
            
            if msg_type == "message":
                user_msg = data.get("message", "")
                print(f"[WS] Received: {user_msg}")
                
                # Send thinking status
                await ws.send_json({
                    "type": "status",
                    "status": "thinking"
                })
                
                # Process through JARVIS pipeline
                api_client.add_user_message(user_msg, session_id=session_id)
                
                response = await api_client.chat_with_tools(
                    tool_schemas=tool_registry.schemas,
                    tool_executor=tool_registry.execute,
                    session_id=session_id
                )
                
                # Send response back to Electron
                await ws.send_json({
                    "type": "response",
                    "text": response,
                    "status": "speaking"
                })
                
                print(f"[WS] Sent response: {response[:100]}")
                
            elif msg_type == "slash_command":
                cmd = data.get("command", "")
                # Handle basic slash commands
                if cmd == "/exit":
                    await ws.send_json({
                        "type": "response",
                        "text": "Goodbye, sir.",
                        "status": "idle"
                    })
                else:
                    await ws.send_json({
                        "type": "response",
                        "text": f"Command: {cmd}",
                        "status": "idle"
                    })
                    
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