# JARVIS Architecture

## System Overview

```
User (voice/text)
      ↓
┌─────────────────────────────────────┐
│           INTERFACES                │
│  CLI Terminal  │  Electron Desktop  │
│  (jarvis/cli)  │  (jarvis-desktop/) │
└────────────────┬────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│         FASTAPI WEBSOCKET           │
│           (jarvis/api.py)           │
│     WebSocket + REST endpoints      │
└────────────────┬────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│          CORE PIPELINE              │
│   JarvisAPIClient (api_client.py)   │
│   ┌─────────────────────────────┐   │
│   │  LLM Provider (llm_provider)│   │
│   │  NVIDIA / Groq / Anthropic  │   │
│   └─────────────────────────────┘   │
│   ┌─────────────────────────────┐   │
│   │  Tool Registry (tools.py)   │   │
│   │  ~59 tools registered       │   │
│   └─────────────────────────────┘   │
└────────────────┬────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│           DATA LAYER                │
│  SQLite DB    │  config.yaml        │
│  (memory,     │  .env               │
│   projects,   │  jarvis/data/       │
│   reminders,  │                     │
│   trading)    │                     │
└────────────────┬────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│        EXTERNAL SERVICES            │
│  NVIDIA NIM  │  GitHub (gh CLI)     │
│  Weather API │  Google Calendar     │
│  DuckDuckGo  │  Gmail              │
└─────────────────────────────────────┘
```

## Tool Categories
| Category | Count | File |
|----------|-------|------|
| File operations | 7 | tools.py |
| App control | 3 | tools.py |
| Browser | 3 | tools.py |
| System | 2 | tools.py |
| Clipboard | 2 | tools.py |
| GitHub/Git | 18 | tools.py |
| System files | 7 | tools.py |
| Trading | 4 | trading.py |
| Memory | 4 | memory.py |
| Projects | 3 | memory.py |
| Web search | 2 | tools.py |

## Data Flow: Tool Execution
1. User sends message
2. `JarvisAPIClient.chat_with_tools()` called
3. LLM API receives message + 59 tool schemas
4. LLM decides which tool(s) to call
5. `ToolRegistry.execute()` runs real function/subprocess
6. Tool result injected back into conversation
7. Second LLM call generates natural language response
8. Response spoken via TTS + displayed in UI

## Key Design Decisions
- **Single pipeline**: All messages route through tool-calling pipeline
- **No hardcoded keyword matching**: LLM decides when to execute tools
- **Ground truth verification**: Tools verify actual execution outcomes
- **Session isolation**: Independent conversation contexts across interfaces
- **Provider abstraction**: Seamlessly swap LLM providers via `JARVIS_LLM_PROVIDER`
- **Error recovery**: Exponential backoff retries and circuit breaking on external services
