from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Add JARVIS root to path so all imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

active_websocket: WebSocket = None
_cli_instance = None

def get_cli_instance():
    global _cli_instance
    if _cli_instance is None:
        from jarvis.cli import JARVISCLI
        _cli_instance = JARVISCLI()
    return _cli_instance

@app.on_event("startup")
async def startup():
    cli = get_cli_instance()
    if hasattr(cli, 'proactive_monitor') and cli.proactive_monitor:
        cli.proactive_monitor.set_push_callback(push_proactive_alert)
        if not (hasattr(cli.proactive_monitor, 'thread') and cli.proactive_monitor.thread and cli.proactive_monitor.thread.is_alive()):
            cli.proactive_monitor.start()

async def push_proactive_alert(alert_text: str, alert_type: str = 'reminder') -> bool:
    """Proactive alerts push to frontend over WebSocket without user asking."""
    global active_websocket
    if active_websocket:
        try:
            await active_websocket.send_json({
                'type': 'proactive_alert',
                'text': alert_text,
                'alert_type': alert_type
            })
            return True
        except Exception as e:
            print(f"[API] Error pushing alert: {e}")
            return False
    return False

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global active_websocket
    await websocket.accept()
    active_websocket = websocket
    print("[API] Electron frontend connected")
    
    # Generate dynamic boot greeting
    cli = get_cli_instance()
    greeting_text = "JARVIS online and standing by."
    if cli and hasattr(cli, 'proactive_monitor') and cli.proactive_monitor:
        try:
            user_title = getattr(cli.api_client, 'user_title', 'sir')
            if hasattr(cli.proactive_monitor, 'get_boot_greeting'):
                greeting_text = cli.proactive_monitor.get_boot_greeting(user_title)
        except Exception as e:
            print(f"[API] Error generating boot greeting: {e}")

    # Send boot status
    await websocket.send_json({
        'type': 'status',
        'status': 'connected',
        'message': greeting_text
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get('type', 'message')
            
            if msg_type == 'message':
                await handle_chat_message(websocket, data)
            elif msg_type == 'slash_command':
                await handle_slash_command(websocket, data)
            elif msg_type == 'voice_input':
                await handle_voice_input(websocket, data)
                
    except Exception as e:
        print(f"[API] Connection closed: {e}")
        active_websocket = None

async def handle_chat_message(websocket: WebSocket, data: dict):
    user_message = data.get('message', '')
    
    await websocket.send_json({'type': 'status', 'status': 'thinking'})
    
    try:
        cli = get_cli_instance()
        tx_before = len(getattr(cli.tools, 'last_transactions', []))
        
        response_text = await cli.process_command(user_message)
        if not response_text or not str(response_text).strip():
            response_text = "Done, sir."

        tx_after = getattr(cli.tools, 'last_transactions', [])
        tool_calls = []
        if len(tx_after) > tx_before:
            for tx in tx_after[tx_before:]:
                tool_calls.append({
                    'name': tx.get('tool', 'tool'),
                    'result': tx.get('result', '')
                })

        await websocket.send_json({
            'type': 'response',
            'text': str(response_text),
            'tool_calls': tool_calls,
            'status': 'speaking'
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        await websocket.send_json({
            'type': 'response',
            'text': f'Something went wrong, sir. ({str(e)})',
            'status': 'idle'
        })

async def handle_slash_command(websocket: WebSocket, data: dict):
    command = data.get('command', '')
    
    await websocket.send_json({'type': 'status', 'status': 'thinking'})
    
    try:
        cli = get_cli_instance()
        result = await cli._handle_slash_command(command)
        if not result or not str(result).strip():
            result = "Command executed, sir."
            
        await websocket.send_json({
            'type': 'command_response',
            'text': str(result),
            'command': command,
            'status': 'idle'
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        await websocket.send_json({
            'type': 'command_response',
            'text': f'Error executing slash command: ({str(e)})',
            'command': command,
            'status': 'idle'
        })

async def handle_voice_input(websocket: WebSocket, data: dict):
    voice_text = data.get('text', '')
    if voice_text:
        data['message'] = voice_text
        await handle_chat_message(websocket, data)

# External chat API endpoints
@app.post("/chat")
async def chat_endpoint(request: dict):
    # Accepts: { "message": "...", "source": "external" }
    # Processes through full JARVIS pipeline
    # Returns: { "response": "...", "tool_calls": [] }
    message = request.get('message', '')
    source = request.get('source', 'unknown')
    print(f"[API] Chat from {source}: {message}")
    
    cli = get_cli_instance()
    tx_before = len(getattr(cli.tools, 'last_transactions', []))
    
    loop = asyncio.get_event_loop()
    response_text = await cli.process_command(message)
    if not response_text or not str(response_text).strip():
        response_text = "Done, sir."

    tx_after = getattr(cli.tools, 'last_transactions', [])
    tool_calls = []
    if len(tx_after) > tx_before:
        for tx in tx_after[tx_before:]:
            tool_calls.append({
                'name': tx.get('tool', 'tool'),
                'result': tx.get('result', '')
            })
    
    # Also push to Electron GUI if connected
    if active_websocket:
        try:
            await active_websocket.send_json({
                'type': 'proactive_alert',
                'text': f'[{source.upper()}] {response_text}',
                'alert_type': 'agent'
            })
        except Exception as e:
            print(f"[API] Error pushing to websocket: {e}")
    
    return {"response": str(response_text), 
            "tool_calls": tool_calls}


@app.post("/actions/execute")
async def execute_action(request: dict):
    # Accepts: { "action": "/diagnose", "params": {...} }
    # Executes a slash command
    # Returns: { "result": "...", "success": true/false }
    action = request.get('action', '')
    params = request.get('params', {}) or request.get('args', {})
    
    if not action:
        return {"result": "action required", "success": False}
    
    try:
        cli = get_cli_instance()
        
        # Build slash command from action and params
        if params:
            import json
            cmd = action + " " + json.dumps(params)
        else:
            cmd = action
        
        result = await cli._handle_slash_command(cmd)
        if not result or not str(result).strip():
            result = "Command executed, sir."
        
        return {
            "result": str(result),
            "success": True
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"result": str(e), "success": False}


@app.get("/status")
async def full_status():
    # Returns projects, reminders, fact count, active threads
    from jarvis.memory import MemoryManager
    from jarvis.projects import get_active_projects_summary
    memory = MemoryManager()
    
    cli = get_cli_instance()
    is_monitor_alive = False
    if hasattr(cli, 'proactive_monitor') and cli.proactive_monitor:
        if hasattr(cli.proactive_monitor, 'thread') and cli.proactive_monitor.thread:
            is_monitor_alive = cli.proactive_monitor.thread.is_alive()
        else:
            is_monitor_alive = True
            
    return {
        "status": "healthy",
        "projects": get_active_projects_summary(),
        "reminders": memory.get_pending_reminders(),
        "fact_count": memory.get_fact_count(),
        "threads": {
            "proactive_monitor": is_monitor_alive,
        }
    }


@app.post("/push-alert")
async def push_alert(request: dict):
    # External system calls this to push alerts to JARVIS GUI
    # Accepts: { "message": "...", "severity": "info|warning|critical" }
    message = request.get('message', '')
    severity = request.get('severity', 'info')
    
    # Speak it via TTS if available
    try:
        cli = get_cli_instance()
        if hasattr(cli, 'voice_manager') and cli.voice_manager:
            speak_fn = getattr(cli.voice_manager, 'speak_text', None) or getattr(cli.voice_manager, 'speak', None)
            if speak_fn:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, speak_fn, message)
    except Exception as e:
        print(f"[API] TTS warning: {e}")
    
    # Push to Electron GUI
    if active_websocket:
        try:
            await active_websocket.send_json({
                'type': 'proactive_alert',
                'text': message,
                'alert_type': f'agent_{severity}'
            })
            return {"pushed": True}
        except Exception as e:
            print(f"[API] Error pushing alert to websocket: {e}")
            return {"pushed": False, "error": str(e)}
    else:
        # GUI not connected — log it
        print(f"[ALERT] GUI offline, logged: {message}")
        with open('agent_alerts.log', 'a', encoding='utf-8') as f:
            f.write(f"{message}\n")
        return {"pushed": False, "logged": True}


# REST endpoints for live sidebar data
@app.get("/projects")
async def get_projects():
    try:
        cli = get_cli_instance()
        return cli.project_manager.get_active_projects_summary()
    except Exception as e:
        return []

@app.get("/reminders")  
async def get_reminders():
    try:
        cli = get_cli_instance()
        reminders = cli.memory.get_reminders()
        return [r for r in reminders if not r.get('completed')]
    except Exception as e:
        return []

@app.get("/watchlist")
async def get_watchlist():
    try:
        cli = get_cli_instance()
        return cli.memory.get_price_watches()
    except Exception as e:
        return []

@app.get("/vitals")
async def get_vitals():
    try:
        import psutil
        import time
        from jarvis.system_monitor import SystemMonitor
        monitor = SystemMonitor()
        snapshot = monitor.get_system_snapshot()
        
        boot_time = psutil.boot_time()
        uptime_seconds = int(time.time() - boot_time)
        snapshot["uptime_seconds"] = uptime_seconds
        
        cli = get_cli_instance()
        tx = getattr(cli.tools, 'last_transactions', [])
        snapshot["commands_today"] = len(tx)
        snapshot["tool_calls_today"] = len([t for t in tx if t.get('tool')])
        return snapshot
    except Exception as e:
        return {
            "cpu_pct": 0,
            "ram_pct": 0,
            "ram_used_gb": 0,
            "ram_total_gb": 0,
            "uptime_seconds": 0,
            "commands_today": 0,
            "tool_calls_today": 0
        }


def free_port(port: int = 8765):
    """Find and terminate any stale background process listening on the target port"""
    try:
        import subprocess
        res = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=3
        )
        if res.returncode == 0:
            current_pid = os.getpid()
            for line in res.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    pid_str = parts[-1]
                    if pid_str.isdigit() and int(pid_str) != current_pid:
                        print(f"[API] Freeing port {port} by terminating stale PID {pid_str}...")
                        subprocess.run(["taskkill", "/F", "/PID", pid_str], capture_output=True, timeout=3)
    except Exception as e:
        print(f"[API] Port cleanup warning: {e}")

if __name__ == "__main__":
    free_port(8765)
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
