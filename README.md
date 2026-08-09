<div align="center">

# J.A.R.V.I.S.
### Just A Rather Very Intelligent System

*A personal AI assistant featuring an Electron + React desktop UI, voice TTS engine, dual SQLite & FAISS vector memory, native GitHub & Git integration, system diagnostics, proactive awareness, and full PC control — powered by NVIDIA Nemotron.*

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![Electron](https://img.shields.io/badge/Electron-Desktop-47848F?style=flat-square&logo=electron)
![React](https://img.shields.io/badge/React-18.x-61DAFB?style=flat-square&logo=react)
![NVIDIA](https://img.shields.io/badge/NVIDIA-Nemotron--3--Ultra--550b-76B900?style=flat-square&logo=nvidia)
![Memory](https://img.shields.io/badge/Memory-SQLite%20%2B%20FAISS-003B57?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square)

**Built by [Nived](https://github.com/nivedjkr)**

</div>

---

## What is JARVIS?

JARVIS is a local AI assistant that runs directly on your machine — accessible via a sleek Electron + React desktop application or an interactive terminal CLI. Powered by the **NVIDIA Nemotron** LLM API, JARVIS goes beyond standard chatbot wrappers by providing an intelligent local operating system: voice output, persistent relational and vector memory, real-time hardware diagnostics, native GitHub and Git workflows, proactive awareness monitoring, and safe system execution tools.

---

## Key Features

### 🖥️ Electron Desktop App & Animated Node Network Orb
- **Sleek Dark Interface**: Built with Electron, React, and Vite using a glassmorphic design system.
- **4-State Animated Node Network Orb**: Canvas visualizer providing real-time feedback across `idle`, `listening`, `thinking`, and `speaking` states.
- **System Vitals Panel**: Live hardware monitoring for CPU utilization, RAM usage, and GPU metrics.
- **Directives & Protocol Control**: Interactive side panel to view system directives and trigger macro protocols.
- **FastAPI WebSocket Bridge**: High-performance bidirectional WebSocket communication (`ws://127.0.0.1:8765/ws`) connecting the Python backend to the React interface.
- **Frameless Window Control**: Custom draggable header bar with native window management (minimize, maximize, close).

### 💻 Full System Access & Local PC Control
- **File & Directory Management**: Create, read, write, list, copy, move, rename, and delete local files and folders.
- **Application Controller (`apps.py`)**: Launch, monitor, and terminate local desktop applications by name.
- **Web & URL Navigator**: Open web pages dynamically, search the web via DuckDuckGo, and scrape structured page text.
- **System Resource Monitoring (`system_monitor.py`)**: Monitor real-time CPU, RAM, GPU, disk storage, and network interfaces.
- **Terminal Shell Integration**: Execute shell commands with safety gate prompts (`tools.confirm_dangerous`) and execution logging.

### 🐙 Native GitHub & Git Workflows (`github_tool.py`)
- **Native `gh` CLI Integration**: Search repositories, list/create issues, check PR status, and monitor GitHub Actions CI runs.
- **Full Git Commands**: Check repository status, create/switch branches, inspect commit logs, view diffs, commit, and push.
- **Safety Gates**: Automated diff preview confirmation before executing dangerous git mutations or pushes.

### 🗣️ Voice Output Engine & Personality (`voice.py`)
- **Edge-TTS Voice Output**: High-quality natural voice output using `edge-tts` (British voice profile `en-GB-RyanNeural`).
- **Time-Aware Boot Greetings**: Contextual greeting on startup ("Good morning, sir. All systems operational.")
- **Speech Interruption**: Automatic mid-sentence speech cancellation when new user input is detected.
- **Voice Toggle**: Quick slash commands (`/speak on|off`) and UI buttons to toggle voice output dynamically.

### 🧠 Dual Memory Architecture (SQLite + Semantic Vector Search)
- **Persistent SQLite Store (`memory.py`)**: Saves user facts, preferences, system state, and session history across restarts.
- **Semantic Vector Search (`semantic_memory.py`)**: FAISS vector index backed by `sentence-transformers` embeddings for semantic similarity lookup.
- **Automatic Fact Extraction**: Extracts facts and preferences from conversation with conflict resolution.

### ⚡ Proactive Intelligence & System Diagnostics
- **Awareness Engine (`awareness.py`)**: Background monitoring of news topics, system status, calendar events, and stock velocity anomalies.
- **System Diagnostics (`diagnostics.py`)**: Automated health checks, self-healing process inspection, and diagnostic reports (`/diagnose`).
- **Projects & Task Engine (`projects.py`)**: Workspace manager, project switcher, task tracking, notes, and decision logging.
- **Automation Protocols (`protocols.py`)**: Automated multi-step macro protocol execution.
- **Google Services Integration (`calendar_service.py`, `email_service.py`, `google_auth.py`)**: Google Calendar event synchronization and Gmail service integration.

---

## Architecture

```
JARVIS/
├── .env.example                ← Environment variables template
├── config.yaml                 ← Global configuration (API, Voice, Awareness, Tools)
├── requirements.txt            ← Python dependencies (FastAPI, FAISS, edge-tts, etc.)
├── README.md                   ← Master project documentation
│
├── jarvis/                     ← Core Python Backend Engine
│   ├── __init__.py             ← Package initialization
│   ├── __main__.py             ← CLI entrypoint wrapper
│   ├── api.py                  ← FastAPI + WebSocket bridge server (port 8765)
│   ├── api_client.py           ← NVIDIA NIM API client (Nemotron model)
│   ├── apps.py                 ← Application controller & launcher
│   ├── awareness.py            ← Proactive awareness & news surfacing engine
│   ├── calendar_service.py     ← Google Calendar integration & event manager
│   ├── cli.py                  ← Terminal CLI runner with rich formatting
│   ├── diagnostics.py          ← System diagnostics, health checks & self-healing
│   ├── email_service.py        ← Email service & Gmail integration
│   ├── github_tool.py          ← GitHub CLI (`gh`) & repository workflow manager
│   ├── google_auth.py          ← Google OAuth 2.0 authentication helper
│   ├── mcp_client.py           ← Model Context Protocol (MCP) client bridge
│   ├── memory.py               ← SQLite persistent state & fact memory engine
│   ├── projects.py             ← Task manager, project switcher & decision log
│   ├── protocols.py            ← Automated multi-step macro protocols runner
│   ├── semantic_memory.py      ← FAISS vector index & sentence-transformer embeddings
│   ├── system_monitor.py       ← Hardware monitor (CPU, RAM, GPU, Disk, Network)
│   ├── tools.py                ← Unified tool registry with safety confirmation gates
│   ├── ui.py                   ← Rich CLI UI layout & formatting helpers
│   ├── voice.py                ← Voice TTS engine (edge-tts British Ryan profile)
│   ├── weather.py              ← OpenWeatherMap live weather integration
│   ├── data/                   ← Databases, JSON cache, and FAISS vector index
│   └── tests/                  ← Unit tests & manual feature test suite
│
└── jarvis-desktop/             ← Electron + React Desktop Application
    ├── package.json            ← Node dependencies & script runners
    ├── vite.config.js          ← Vite build configuration
    ├── electron/
    │   ├── main.js             ← Electron main process & Python backend launcher
    │   └── preload.js          ← Secure IPC context bridge
    └── src/
        ├── App.jsx             ← React application root & WebSocket state manager
        ├── index.css           ← Modern dark glassmorphic global styles
        ├── main.jsx            ← React entrypoint
        └── components/
            ├── ChatLog.jsx     ← Interactive message log with markdown rendering
            ├── DirectivesPanel.jsx ← Macro protocol directives & system control panel
            ├── InputBar.jsx    ← Prompt bar with voice toggle & quick actions
            ├── Orb.jsx         ← 4-state animated Node Network Orb (Idle/Listening/Thinking/Speaking)
            ├── Sidebar.jsx     ← Navigation & module switcher sidebar
            ├── SystemVitals.jsx← Real-time CPU, RAM, GPU hardware status panel
            └── TitleBar.jsx    ← Custom frameless window header bar
```

---

## Setup & Quickstart

### Prerequisites
- **Python**: 3.10+
- **Node.js**: 18+ (for Electron desktop app)
- **Git** & **GitHub CLI (`gh`)**: (for repository workflows)
- **OS**: Windows 10/11 (primary support), Linux/macOS

### 1. Installation

```bash
# Clone repository
git clone https://github.com/nivedjkr/jarvis-assistant.git
cd jarvis-assistant

# Create Python virtual environment
python -m venv venv
venv\Scripts\activate        # On Windows (or source venv/bin/activate on Linux/macOS)

# Install backend dependencies
pip install -r requirements.txt

# Set up environment variables
copy .env.example .env       # Edit .env and insert your NVIDIA_NIM_API_KEY
```

### 2. Running JARVIS

#### Option A: Electron Desktop Application (Recommended)

```bash
cd jarvis-desktop
npm install
npm run dev
```
*The Electron desktop app automatically launches and manages the Python backend server in the background.*

#### Option B: Terminal CLI Mode

```bash
python -m jarvis.cli
```

---

## Environment Variables

| Key | Purpose | Required | Where to get |
|-----|---------|----------|--------------|
| `NVIDIA_NIM_API_KEY` | LLM Inference (Nemotron-3-Ultra-550B / Llama 3.1) | **Yes** | [build.nvidia.com](https://build.nvidia.com) |
| `OPENWEATHER_API_KEY` | Live weather updates & alerts | Optional | [openweathermap.org](https://openweathermap.org) |
| `NEWSAPI_KEY` | Global news monitoring | Optional | [newsapi.org](https://newsapi.org) |
| `PICOVOICE_ACCESS_KEY` | Wake word detection | Optional | [console.picovoice.ai](https://console.picovoice.ai) |

---

## Slash Commands

| Command | Action |
|---------|--------|
| `/help` | Display command summary and usage examples |
| `/exit` | Exit the CLI assistant |
| `/clear` | Clear terminal screen |
| `/tools` | List all active backend execution tools |
| `/history` | View recent conversation history |
| `/context` | Display session token count and message stats |
| `/context clear` | Clear active conversation context |
| `/diagnose` | Run comprehensive system health check & diagnostics |
| `/speak on\|off` | Toggle voice TTS output |

---

## Design Philosophy

JARVIS is built on deterministic tool execution. Every real-world action — inspecting files, launching apps, querying hardware stats, fetching GitHub issues, and managing database records — relies on structured tool execution and strict safety gates rather than unverified LLM approximations.

---

## License

MIT License — free to use, modify, and extend.

---

<div align="center">
<sub>Built by Nived · Powered by NVIDIA NIM · Electron + React · Python · SQLite + FAISS · edge-tts</sub>
</div>

