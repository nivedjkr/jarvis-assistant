<div align="center">

# J.A.R.V.I.S.
### Just A Rather Very Intelligent System

*A personal AI assistant with voice, memory, GitHub integration, Electron desktop app, and full system control — powered by NVIDIA Nemotron.*

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![Electron](https://img.shields.io/badge/Electron-Desktop-47848F?style=flat-square&logo=electron)
![NVIDIA](https://img.shields.io/badge/NVIDIA-Nemotron--3--Ultra--550b-76B900?style=flat-square&logo=nvidia)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square)

**Built by [Nived](https://github.com/nivedjkr) — age 20**

</div>

---

## What is JARVIS?

JARVIS is a local AI assistant that runs on your machine — via interactive terminal or a sleek Electron desktop app. Powered by the **NVIDIA Nemotron-3-Ultra-550B** model, it features voice output, persistent SQLite & vector memory, full local PC control, native GitHub integration, and specialized tools for software engineering, trading, and studying.

Not a wrapper. Not a chatbot. A personal operating system.

---

## Key Features

### 🖥️ Electron Desktop App & Node Network Orb
- Sleek dark visual interface with interactive animated node network orb
- 4-state orb visual feedback: `idle`, `listening`, `thinking`, `speaking`
- Custom frameless window design with native titlebar control
- Real-time bidirectional WebSocket bridge (`ws://127.0.0.1:8765/ws`) to Python backend
- Full feature parity with CLI terminal mode

### 💻 Full System Access & Local PC Control
- File & Directory Manager: create, read, write, copy, move, rename, delete files and directories
- Application Controller: launch and close local applications by name
- Web & URL Navigator: open websites and web searches dynamically
- System Resource & Diagnostics: monitor CPU, RAM, GPU, disk, and network interfaces
- Terminal Shell Integration: run shell commands with configurable confirmation safety gates and logging

### 🐙 Native GitHub & Git Integration
- Native `gh` CLI integration: list repos, search issues, monitor PRs, check CI run status
- Full Git workflow commands: check status, create/switch branches, pull, commit, and push
- Automated safety gates (`tools.confirm_dangerous`) with diff preview confirmation before pushes
- GitHub repository details, release tags, and gist management

### 🗣️ Voice Output & Personality
- Voice TTS — speaks responses using `edge-tts` (British voice profile)
- Time-aware boot greetings and contextual status reports
- JARVIS personality — dry wit, polite demeanor, addresses you as "sir"
- Mid-sentence speech interrupt by user input

### 🧠 Dual Memory Architecture (SQLite + Semantic Vector Search)
- Persistent SQLite database — stores user facts, preferences, and system state
- Semantic Memory — vector-based embedding search using FAISS and Sentence Transformers
- Automatic fact extraction from conversation with contradiction resolution
- Slash commands: `/remember`, `/forget`, `/whoami`, `/profile`

### 📈 Trading, Student & Developer Suites
- **Developer**: Stack trace error explanation, project switcher, TODO manager, GitHub/Git workflows
- **Trading**: Live watchlist alerts, trade log journal, earnings calendar
- **Student**: Spaced repetition flashcards, text-extracted PDF summarizer, deadline tracker
- **Internship Hunter**: Job board monitoring, application pipeline tracker, interview research briefings

---

## Architecture

```
jarvis/                          ← Python Backend Core & Tools
├── cli.py                       ← Terminal CLI interface
├── api.py                       ← FastAPI WebSocket bridge server (port 8765)
├── api_client.py                ← NVIDIA NIM API client (Nemotron model)
├── tools.py                     ← Unified tool registry & schema system
├── memory.py                    ← SQLite memory engine
├── semantic_memory.py           ← FAISS & vector search memory
├── voice.py                     ← Text-to-speech engine (edge-tts)
├── github_tool.py               ← GitHub CLI integration
├── proactive.py                 ← Background monitor & notifications
├── trading.py                   ← Trading watchlist & journal
├── internships.py               ← Job board monitor
└── calendar_service.py          ← Google Calendar integration

jarvis-desktop/                  ← Electron + React Frontend
├── electron/main.js             ← Electron main process & Python backend launcher
├── electron/preload.js          ← Secure IPC bridge
└── src/
    ├── App.jsx                  ← Main app container
    ├── components/Orb.jsx       ← 4-state animated node network orb
    ├── components/ChatLog.jsx   ← Chat log & response rendering
    └── components/InputBar.jsx  ← User prompt input bar
```

---

## Setup & Quickstart

### Prerequisites
- **Python**: 3.10+
- **Node.js**: 18+ (for Electron app)
- **Git** & **GitHub CLI (`gh`)**: (for GitHub tools)
- **OS**: Windows 10/11 (primary support), Linux/macOS

### 1. Installation

```bash
git clone https://github.com/nivedjkr/jarvis-assistant.git
cd jarvis-assistant

# Create Python virtual environment
python -m venv venv
venv\Scripts\activate        # On Windows

# Install backend dependencies
pip install -r requirements.txt

# Set up environment variables
copy .env.example .env       # Edit .env and set your NVIDIA_NIM_API_KEY
```

### 2. Running JARVIS

#### Option A: Electron Desktop App (Recommended)

```bash
cd jarvis-desktop
npm install
npm run dev
```
*The Electron app automatically launches and manages the Python backend process in the background.*

#### Option B: Terminal CLI Mode

```bash
python -m jarvis.cli
```

---

## Environment Variables

| Key | Purpose | Required | Where to get |
|-----|---------|----------|--------------|
| `NVIDIA_NIM_API_KEY` | LLM Inference (Nemotron-3-Ultra-550B) | **Yes** | [build.nvidia.com](https://build.nvidia.com) |
| `OPENWEATHER_API_KEY` | Weather alerts | Optional | [openweathermap.org](https://openweathermap.org) |
| `NEWSAPI_KEY` | Global news monitoring | Optional | [newsapi.org](https://newsapi.org) |
| `PICOVOICE_ACCESS_KEY` | Wake word detection | Optional | [console.picovoice.ai](https://console.picovoice.ai) |

---

## Slash Commands

| Category | Commands |
|----------|----------|
| Core | `/help`, `/clear`, `/exit`, `/history` |
| Voice | `/speak on\|off`, `/mute` |
| Memory | `/remember`, `/forget`, `/profile`, `/whoami` |
| Reminders | `/reminders`, `/deadline add`, `/deadlines` |
| Apps | `/apps`, `/addapp`, `/removeapp` |
| Protocols | `/protocol list\|run\|create\|edit\|delete` |
| Diagnostics | `/diagnose`, `/why` |
| Developer | `/github issues\|prs\|ci\|repo` |
| Trading | `/watch`, `/trade log\|review` |
| Projects | `/projects`, `/task`, `/note`, `/decide` |

---

## Design Philosophy

JARVIS catches its own mistakes. Every feature that reports real-world data (files, system state, GitHub issues, reminders) is grounded in deterministic tool execution — never LLM-generated approximations.

---

## License

MIT — use it, fork it, build on it.

---

<div align="center">
<sub>Built by Nived · NVIDIA NIM · Electron + React · Python · SQLite · edge-tts</sub>
</div>
