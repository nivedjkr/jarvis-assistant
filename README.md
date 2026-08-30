<div align="center">

# J.A.R.V.I.S. Mk 5
### Just A Rather Very Intelligent System

*An autonomous personal AI intelligence system featuring a Mark 5 High-Performance Network & Async Engine, Mark 5.2 Persistent Mission Next Action Engine, Mark 5 Proactive Follow-Up Engine, Persistent Mission Intelligence & task tracking, unified Tool Call Normalization, Electron + React desktop UI, Tailscale Mobile PWA integration, live Gmail integration & Email UI panel, voice TTS engine, dual SQLite & FAISS vector memory, native GitHub & Git workflows, system diagnostics, and full PC control — powered by NVIDIA Nemotron & Google Gemini.*

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![Electron](https://img.shields.io/badge/Electron-Desktop-47848F?style=flat-square&logo=electron)
![Mobile PWA](https://img.shields.io/badge/Mobile-PWA%20Tailscale-purple?style=flat-square&logo=pwa)
![React](https://img.shields.io/badge/React-18.x-61DAFB?style=flat-square&logo=react)
![NVIDIA](https://img.shields.io/badge/NVIDIA-Nemotron--3--Ultra--550b-76B900?style=flat-square&logo=nvidia)
![Gmail](https://img.shields.io/badge/Gmail-Google%20OAuth-EA4335?style=flat-square&logo=gmail)
![Memory](https://img.shields.io/badge/Memory-SQLite%20%2B%20FAISS-003B57?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Version](https://img.shields.io/badge/Release-Mk%205.3.0-brightgreen?style=flat-square)


**Built by [Nived](https://github.com/nivedjkr)**

</div>

---

## 📚 Documentation & Architecture

Comprehensive technical documentation is available in the [`docs/`](docs/) directory:

- 🏗️ **[Architecture Guide](docs/ARCHITECTURE.md)**: System overview, ASCII data flow diagrams, and design principles.
- ⚡ **[Tool Reference Catalog](docs/TOOLS.md)**: Complete catalog of all ~59 registered tool schemas, descriptions, and natural language triggers.
- ⚙️ **[Setup & Installation Guide](docs/SETUP.md)**: Step-by-step setup guide for CLI, Electron UI, environment configuration, and live debug dashboard.

---

## Key Features

### ⚡ Mark 5 High-Performance Network & Async Engine (`llm_provider.py` & `diagnostics.py`)
- **Persistent HTTP Connection Pooling**: Shared persistent `httpx.AsyncClient` keep-alive pool (`max_keepalive_connections=30`, `max_connections=100`, `keepalive_expiry=300s`) across all LLM providers (NVIDIA NIM, Groq, Ollama, Gemini), reducing connection handshake overhead by up to 3x per request.
- **Non-Blocking Async System Diagnostics**: Offloads blocking system & CLI checks to worker threads (`asyncio.to_thread`), preventing event-loop stalls during WebSocket connection startup.

### 🎯 Mark 5.2 Persistent Mission Next Action Engine (`mission_manager.py`)
- **Deterministic Task Selection**: `get_next_actionable_task(mission_id)` evaluates real SQLite-persisted mission state and deterministically selects the single next actionable task without executing actions.
- **Dependency Graph Resolution**: Resolves multi-tier prerequisite task relationships (`depends_on`), selecting dependent tasks only after all prerequisites are marked `COMPLETED`.
- **Blocker & Inactive State Defense**: Safely ignores inactive/paused/proposed missions and excludes blocked tasks (`WAITING`, incomplete dependencies), returning structured `NextActionResult` reason codes (`MISSION_NOT_ACTIVE`, `ALL_TASKS_COMPLETED`, `WAITING_ON_DEPENDENCIES`, `ALL_TASKS_BLOCKED`).
- **Priority & Tie-Breaker Ranking**: Deterministically ranks candidate tasks by priority weight (`CRITICAL` $\rightarrow$ `HIGH` $\rightarrow$ `MEDIUM` $\rightarrow$ `LOW` / numeric), unlock impact (count of downstream dependent tasks), creation order, and task ID string tie-breakers.
- **Long-Term Objective Detection**: `MissionDetector` identifies ongoing goals (internships, project launches, skill mastery) while filtering out casual talk and errands.
- **Explicit Approval Gate**: Missions are created in `PROPOSED` state and require explicit user approval (`/confirm` or `/mission approve <id>`) before activation.
- **Controlled State Machines**: Validated status transitions for `MissionStatus` (`PROPOSED`, `ACTIVE`, `PLANNING`, `EXECUTING`, `WAITING`, `PAUSED`, `COMPLETED`, `FAILED`, `CANCELLED`) and `MissionTaskStatus` (`PENDING`, `READY`, `RUNNING`, `WAITING`, `COMPLETED`, `FAILED`, `CANCELLED`).
- **SQLite Persistence**: Stores missions and structured tasks in SQLite database (`missions` & `mission_tasks` in `jarvis.db`), surviving application restarts.
- **Slash Commands & REST APIs**: `/missions`, `/mission <id>`, `/mission pause|resume|cancel|approve`, and REST endpoints (`GET /missions`, `POST /missions/{id}/approve`).

### 🚀 Mark 5 Proactive Follow-Up Engine (`proactive_engine.py`)
- **Non-Blocking Background Intelligence**: Operates independently after main response turns are delivered without blocking user interaction.
- **Relevance & Value Gates**: Evaluates prompts against relevance rules and validates findings for novelty, actionable utility, and non-redundancy.
- **Multi-Source Investigation**: Conducts background searches across `web_search_live`, `search_obsidian`, and project files with 15s timeout protection.
- **Natural Proactive Messages**: Delivers separate follow-up messages starting with *"One more thing, sir..."* over WebSocket event streams.

### 🛠️ Unified Tool Call Normalization Layer (`tool_normalizer.py`)
- **Multi-Format Parsing**: Normalizes native OpenAI `tool_calls` and text-based JSON tool call formats (`tool`/`args`, `name`/`arguments`, `action`/`action_input`, JSON arrays, markdown-wrapped JSON).
- **Strict Schema Validation**: Validates tool names against registered capabilities and parameter types.
- **Final Output Filter**: Prevents raw JSON tool call strings from ever reaching the user or frontend.

- **Google OAuth2 Authentication**: Secure Google OAuth authentication supporting Gmail read & send scopes.
- **`EmailPanel.jsx` Component**: Real-time glassmorphic UI cards rendering unread inbox count, sender, subject line, 2-line snippet preview, date, and urgency tags (`URGENT`, `NORMAL`, `NOISE`).
- **Manual Refresh Button**: Interactive `↻` header control to re-sync Gmail inbox on demand via WebSocket.
- **2-Phase Safe Email Sending**: 
  1. *Draft Phase*: Displays a `CONFIRMATION REQUIRED` preview card with `To`, `Subject`, and `Body`.
  2. *Confirmation Phase*: Asking `"yes"` or `"confirm"` invokes Gmail API delivery.
- **Conversational & Slash Tools**: Supports `/email`, `/email summary`, `"check my email"`, `"read email 1"`, and `"send email"`.

### 🖥️ Electron Desktop App & Animated Node Network Orb
- **Sleek Dark Interface**: Built with Electron, React, and Vite using a glassmorphic design system.
- **4-State Animated Node Network Orb**: Canvas visualizer providing real-time feedback across `idle`, `listening`, `thinking`, and `speaking` states.
- **System Vitals Panel**: Live hardware monitoring for CPU utilization, RAM usage, and GPU metrics.
- **Directives & Protocol Control**: Interactive side panel to view system directives and trigger macro protocols.
- **TitleBar Command Controls**: Dragable custom window header with native window management and instant `[?] HELP` command reference modal.
- **FastAPI WebSocket Bridge**: High-performance bidirectional WebSocket communication (`ws://127.0.0.1:8765/ws`) connecting the Python backend to the React interface with tool execution badges (`⚡ TOOL EXECUTED`).

### 🌐 Headless Web Browsing & DOM Rendering (Playwright Engine)
- **Playwright Headless Chromium**: Full single-page application (SPA) and JavaScript DOM rendering (`browse_page`, `browse_click`, `browse_screenshot`, `browse_extract_links`, `browse_close`).
- **Prompt-Injection Defense**: Automatic `<untrusted_external_content source='browser'>` wrapping for all web-harvested text.
- **Resource Management**: 15s per-navigation timeout and 5m idle auto-close timer to prevent orphaned browser processes.
- **Safety Gates & Logging**: `browse_click` target logging and human confirmation gate integration.

### 💻 Full System Access & Local PC Control
- **File & Directory Management**: Create, read, write, list, copy, move, rename, and delete local files and folders.
- **Application Controller (`apps.py`)**: Launch, monitor, and terminate local desktop applications by name.
- **Web & URL Navigator**: Open web pages dynamically, search the web via DuckDuckGo, and scrape structured page text.
- **System Resource Monitoring**: Monitor real-time CPU, RAM, GPU, disk storage, and network interfaces via non-blocking `/vitals`.
- **Terminal Shell Integration**: Execute shell commands with safety gate prompts (`tools.confirm_dangerous`) and execution logging.

### 🔒 Pre-Commit Security & Secrets Protection (`.githooks/pre-commit`)
- **Automated Git Pre-Commit Safeguard**: Dedicated git pre-commit hook blocking accidental commits of secret files (`credentials.json`, `google_token.json`, `*.env`).
- **Comprehensive `.gitignore` Net**: Broader patterns covering `**/credentials*.json`, `**/*token*.json`, and `**/*.env`.
- **Zero-Trust History Audit**: Verified 0 commits touching OAuth secrets across full repository history.

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
- **Proactive Engine (`proactive_engine.py`)**: Background non-blocking relevance & value evaluation, follow-up emission, and multi-source web searches.
- **System Diagnostics (`diagnostics.py`)**: Automated health checks, self-healing process inspection, and diagnostic reports (`/diagnose`).

### 🤖 JARVIS Mk4 Safe Agentic Layer (`jarvis/agents/` & `jarvis/orchestration/`)
- **Modular Logical Agents**: Specialized roles (`PlanningAgent`, `ResearchAgent`, `CodingAgent`, `SystemAgent`, `CommunicationAgent`) extending a unified `BaseAgent`.
- **Direct Execution Bypass**: Simple requests ("What time is it?", "Open Chrome", "Check email") bypass agent orchestration completely with zero latency overhead.
- **Goal Planning & Task Tracking**: Automatically decomposes multi-step goals into subtasks with dependency management and status tracking (`TaskTracker`).
- **Bounded Agentic Loop**: Bounded reasoning-action execution loops (`AgenticLoop`) enforcing maximum iteration caps.
### 📱 Secure Mobile Access & Tailscale PWA (`jarvis-mobile/`)
- **Zero Public Exposure**: Access JARVIS securely over LAN or private [Tailscale](https://tailscale.com) mesh networks without opening public router ports.
- **Standalone PWA Client**: Lightweight, mobile-first Web App (`jarvis-mobile/`) featuring dark glassmorphism, responsive chat log, quick action pills, and Web App Manifest (`manifest.json`) for home screen installation.
- **Voice & Speech Support**: Native Web Speech API voice input (`🎙️`) combined with backend Edge-TTS voice synthesis (`/tts_sentence`).
- **Strict Security Controls**: Enforced `JARVIS_ALLOW_REMOTE=true` flag for `0.0.0.0` binding, CORS regex restricting origins to LAN/Tailscale IP ranges (`100.64.0.0/10`, `*.ts.net`), and mandatory `JARVIS_WS_TOKEN` auth on WebSocket endpoints.

---

## Architecture

```
JARVIS/
├── .env.example                ← Environment variables template
├── .gitignore                  ← Broader gitignore rules for secrets
├── .githooks/                  ← Tracked repository pre-commit security hooks
│   └── pre-commit              ← Hook blocking credentials, tokens, and .env
├── config.yaml                 ← Global configuration (API, Voice, Awareness, Tools)
├── pytest.ini                  ← Pytest configuration targeting jarvis/tests
├── requirements.txt            ← Python dependencies (FastAPI, FAISS, edge-tts, etc.)
├── README.md                   ← Master project documentation
│
├── docs/                       ← Detailed Technical Documentation
│   ├── ARCHITECTURE.md         ← System architecture & data flow diagrams
│   ├── SETUP.md                ← Step-by-step installation & environment configuration
│   └── TOOLS.md                ← Complete reference catalog of ~59 tools
│
├── jarvis/                     ← Core Python Backend Engine
│   ├── __init__.py             ← Package initialization
│   ├── __main__.py             ← CLI entrypoint wrapper
│   ├── agents/                 ← Mk4 Logical Agent Roles
│   │   ├── base_agent.py       ← BaseAgent & AgentResponse classes
│   │   ├── planning_agent.py   ← Request classifier & goal planner
│   │   ├── research_agent.py   ← Web, memory & search research role
│   │   ├── coding_agent.py     ← Software engineering & debug loop role
│   │   ├── system_agent.py     ← System, app & filesystem role
│   │   └── communication_agent.py ← Email, calendar & Obsidian role
│   ├── orchestration/          ← Mk4 Orchestration Pipeline
│   │   ├── task_tracker.py     ← TaskTracker & TaskItem state tracking
│   │   ├── agentic_loop.py     ← Reusable bounded AgenticLoop engine
│   │   └── dispatcher.py       ← AgentDispatcher routing & direct bypass
│   ├── api.py                  ← FastAPI + WebSocket bridge server (port 8765)
│   ├── api_client.py           ← LLM API client with provider abstraction
│   ├── apps.py                 ← Application controller & launcher
│   ├── calendar_service.py     ← Google Calendar integration & event manager
│   ├── cli.py                  ← Terminal CLI runner with rich formatting
│   ├── config_manager.py       ← Central configuration system singleton
│   ├── debug_panel.py          ← Real-time rich developer live debug dashboard
│   ├── diagnostics.py          ← System diagnostics, health checks & self-healing
│   ├── email_service.py        ← Email service & Gmail integration
│   ├── error_recovery.py       ← Circuit breakers & retry mechanism
│   ├── github_tool.py          ← GitHub CLI (`gh`) & repository workflow manager
│   ├── google_auth.py          ← Google OAuth 2.0 authentication helper
│   ├── llm_provider.py         ← Unified provider layer (NVIDIA, Groq, Anthropic, Ollama)
│   ├── mcp_client.py           ← Model Context Protocol (MCP) client bridge
│   ├── memory.py               ← SQLite persistent state, fact memory & CRUD engine
│   ├── semantic_memory.py      ← FAISS vector index & sentence-transformer embeddings
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
            ├── EmailPanel.jsx  ← Live Gmail inbox cards & unread badge panel
            ├── EmailPanel.css  ← Styling for email cards & urgency tags
            ├── InputBar.jsx    ← Prompt bar with voice toggle & quick actions
            ├── Orb.jsx         ← 4-state animated Node Network Orb (Idle/Listening/Thinking/Speaking)
            ├── Sidebar.jsx     ← Navigation & module switcher sidebar
            ├── SystemVitals.jsx← Real-time CPU, RAM, GPU hardware status panel
            └── TitleBar.jsx    ← Custom window header bar with native controls & help button
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

# Configure git pre-commit security hook
git config core.hooksPath .githooks

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

#### Option C: Secure Mobile Web Access (Tailscale PWA)

1. Enable remote access in `.env`:
   ```env
   JARVIS_ALLOW_REMOTE=true
   JARVIS_WS_TOKEN=jarvis_secure_local_token_2026
   ```
2. Start backend server:
   ```bash
   python -m jarvis.api
   ```
3. Open `http://<tailscale-ip>:8765/mobile` on your mobile phone connected to your Tailnet and select **"Add to Home Screen"**.

---

## Environment Variables

| Key | Purpose | Required | Where to get |
|-----|---------|----------|--------------|
| `NVIDIA_NIM_API_KEY` | LLM Inference (Nemotron-3-Ultra-550B / Llama 3.1) | **Yes** | [build.nvidia.com](https://build.nvidia.com) |
| `OPENWEATHER_API_KEY` | Live weather updates & alerts | Optional | [openweathermap.org](https://openweathermap.org) |
| `NEWSAPI_KEY` | Global news monitoring | Optional | [newsapi.org](https://newsapi.org) |
| `PICOVOICE_ACCESS_KEY` | Wake word detection | Optional | [console.picovoice.ai](https://console.picovoice.ai) |

---

## Slash Commands Reference

| Command | Action |
|---------|--------|
| `/help` | Display comprehensive command summary & usage examples |
| `/tools` | List all 59 active backend execution tool schemas |
| `/config` | View, set, save, or reload configuration settings (`show`, `set`, `save`, `reset`) |
| `/memory` | Fact CRUD management (`stats`, `list`, `delete`, `edit`, `clear`, `search`, `export`) |
| `/debug` | Toggle live developer debug panel (`on`, `off`) |
| `/provider` | Switch active LLM provider (`nvidia`, `groq`, `anthropic`, `ollama`) |
| `/email` | Check recent unread emails in Gmail |
| `/email summary` | Get executive email summary briefing |
| `/diagnose` | Run comprehensive multi-service health check & diagnostics |
| `/context` | Display session token count and message stats |
| `/context clear` | Clear active conversation context memory |
| `/history` | View recent conversation history |
| `/speak on\|off` | Toggle voice TTS output |
| `/exit` | Exit the assistant session |

---

## Testing

Run unit test suite:
```bash
python -m pytest -v
```

---

## Design Philosophy

JARVIS is built on deterministic tool execution. Every real-world action — inspecting files, launching apps, querying hardware stats, fetching Gmail messages, managing database records, and committing git changes — relies on structured tool execution and strict safety gates rather than unverified LLM approximations.

---

## License

MIT License — free to use, modify, and extend.

---

<div align="center">
<sub>Built by Nived · Powered by NVIDIA NIM · Electron + React · Python · Gmail API · SQLite + FAISS · edge-tts</sub>
</div>
