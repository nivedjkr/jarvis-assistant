<div align="center">

# J.A.R.V.I.S.
### Just A Rather Very Intelligent System

*A personal AI assistant with voice, memory, and full system control — built for developers, traders, and students.*

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![Electron](https://img.shields.io/badge/Electron-Desktop-47848F?style=flat-square&logo=electron)
![NVIDIA](https://img.shields.io/badge/NVIDIA-NIM_API-76B900?style=flat-square&logo=nvidia)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square)

**Built by [Nived](https://github.com/nivedjkr) — age 20**

</div>

---

## What is JARVIS?

JARVIS is a local AI assistant that runs on your machine — terminal or Electron desktop app. It has voice output, persistent memory, full PC control, and domain-specific tools for trading, studying, and software development.

Not a wrapper. Not a chatbot. A personal operating system.

---

## Features

### Core
- Natural language chat via terminal or Electron desktop app
- Voice TTS — speaks every response (edge-tts, British accent)
- Boot greeting based on time of day
- JARVIS personality — dry wit, addresses you as "sir"
- Interrupt speech mid-sentence by typing

### Memory
- Persistent SQLite memory — remembers facts across sessions
- Auto-extracts facts from conversation
- Contradiction handling — updates stale facts
- `/remember`, `/forget`, `/whoami`, `/profile`

### PC Control
- Open/close applications by name
- Browse websites and URLs
- File and directory operations (create, write, read, copy, rename, move, delete)
- Shell command execution with safety confirmation & logging (`tools.confirm_dangerous`)
- Clipboard control with fail-proof verification and fallbacks

### Protocols & Automation
- Named macro sequences ("work mode", "backup protocol")
- Dry-run preview before execution
- `/protocol list/run/create/edit/delete`

### Trading Tools
- Live price watchlist with alerts
- Percentage-change alerts with news context
- Trade journal — log entries/exits with reasoning
- Earnings calendar for watched tickers
- `/watch AAPL above 200`, `/trade log`, `/trade review`

### Student Tools
- Flashcard system with spaced repetition
- PDF summarizer (real text extraction, not hallucinated)
- Deadline tracker with escalating urgency alerts
- `/flashcard add`, `/review`, `/summarize <pdf>`

### Developer Tools
- GitHub integration via native `gh` CLI (`list_repos`, `list_issues`, `list_prs`, `ci_status`, `repo_info`)
- Git workflow tools (`git_add`, `git_commit`, `git_push` with confirmation gates & diff previews)
- Error explainer — paste stack trace, get plain English fix
- Project switcher — per-project venv, folder, TODOs
- Code snippet library

### Project Database
- Full project tracking (tasks, notes, decisions, timeline)
- Natural language access ("add task to X project")
- Proactive overdue and deadline alerts
- Weekly project review report

### Internship Hunter
- Multi-source job board monitoring (Internshala, LinkedIn RSS, Wellfound)
- Proactive alerts for new matching postings
- Application pipeline tracker with follow-up reminders
- Company research briefing before interviews

### Real-time Monitoring
- Weather alerts (OpenWeatherMap)
- Google Calendar sync + meeting alerts
- Gmail triage — urgent emails spoken proactively
- System resource monitoring (CPU, GPU, RAM, disk, network)
- Security/anomaly monitoring — unusual processes, failed logins

### Diagnostics
- `/diagnose` — real health check of ALL subsystems
- `/why` — shows what tool was called and why
- Confidence-flagged responses on ambiguous inputs

### Electron Desktop App
- Black minimal UI with animated JARVIS orb
- 4-state animation: idle / listening / thinking / speaking
- Frameless window with custom title bar
- Full feature parity with terminal mode

---

## Architecture

```
jarvis/ ← Python CLI backend
├── cli.py ← Main entry point
├── api_client.py ← NVIDIA NIM API client
├── tools.py ← Tool registry
├── memory.py ← SQLite memory system
├── voice.py ← TTS (edge-tts)
├── proactive.py ← Background monitor thread
├── projects.py ← Project database
├── github_tool.py ← GitHub CLI integration
├── trading.py ← Price alerts, trade journal
├── internships.py ← Job board monitoring
├── ui.py ← Rich terminal HUD
└── api.py ← FastAPI WebSocket bridge

jarvis-desktop/ ← Electron + React frontend
├── electron/main.js ← Electron main process
├── electron/preload.js ← IPC bridge
└── src/
    ├── App.jsx
    ├── components/Orb.jsx ← Voice animation
    ├── components/ChatLog.jsx
    └── components/InputBar.jsx
```

---

## Setup

### Prerequisites
- Python 3.10+
- Node.js 18+ (for Electron app)
- Git + gh CLI (for GitHub integration)
- Windows (primary), Linux/Mac partial support

### Terminal Mode

```bash
git clone https://github.com/nivedjkr/jarvis-assistant
cd jarvis-assistant
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env       # Add your API keys
python -m jarvis.cli
```

### Electron Desktop App

```bash
cd jarvis-desktop
npm install
# In a separate terminal: python -m jarvis.api
npm run dev
```

### API Keys Required

| Key | Purpose | Where to get |
|-----|---------|--------------|
| `NVIDIA_NIM_API_KEY` | LLM (required) | build.nvidia.com |
| `OPENWEATHER_API_KEY` | Weather alerts | openweathermap.org |
| `NEWSAPI_KEY` | Global awareness | newsapi.org |
| `PICOVOICE_ACCESS_KEY` | Wake word (optional) | console.picovoice.ai |

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
| Security | `/security status\|allow\|log` |
| Diagnostics | `/diagnose`, `/why` |
| Study | `/flashcard add\|from-file`, `/review`, `/summarize` |
| Developer | `/github issues\|prs\|ci\|repo` |
| Trading | `/watch`, `/trade log\|review` |
| Internships | `/internships`, `/internship apply\|research` |
| Projects | `/projects`, `/task`, `/note`, `/decide` |

---

## Philosophy

JARVIS catches its own mistakes. Every feature that reports real-world data (files, prices, GitHub issues, reminders) is grounded in actual tool calls — never LLM-generated approximations. Three separate hallucination bugs were caught and fixed during development by comparing outputs against known ground truth.

---

## Roadmap

- [ ] Wake word detection (Porcupine "jarvis")
- [ ] Google Calendar + Gmail full integration  
- [ ] Mobile access via Tailscale + SSH
- [ ] Vector memory (semantic search over facts)
- [ ] Multi-agent coordination layer
- [ ] Fine-tuning on personal usage patterns

---

## License

MIT — use it, fork it, build on it.

---

<div align="center">
<sub>Built in one session · NVIDIA NIM · Electron + React · Python · SQLite · edge-tts</sub>
</div>
