# JARVIS - Autonomous AI Assistant & Intelligence System

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Electron](https://img.shields.io/badge/Electron-29%2B-47848F.svg)](https://www.electronjs.org/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)](https://reactjs.org/)
[![NVIDIA NIM](https://img.shields.io/badge/NVIDIA-NIM%20API-76B900.svg)](https://build.nvidia.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An Iron-Man-inspired, dual-interface (Desktop GUI + Terminal CLI) AI assistant packed with real-time proactive system awareness, voice synthesis, autonomous tool execution, project intelligence, and Google Workspace integrations.

---

## Features
- Voice TTS — speaks every response (edge-tts, en-GB-RyanNeural)
- Persistent memory — SQLite, auto-extracts facts across sessions
- PC control — open/close apps, files, shell commands
- Protocol system — named macro sequences
- Trading tools — live price alerts, trade journal, earnings calendar
- Student tools — flashcards, PDF summarizer, deadline tracker
- Developer tools — git status, error explainer, project switcher
- Project database — full task/decision/timeline tracking
- Internship hunter — multi-source job board monitoring
- Real-time monitoring — weather, calendar, email, system resources
- Security monitor — anomaly detection, process monitoring
- Electron desktop app — black minimal UI with JARVIS orb animation
- Ultron bridge — bidirectional OpenClaw agent integration
- GitHub integration — issues, PRs, CI status via gh CLI

---

## Architecture
```
jarvis/                  - Python CLI backend
jarvis-desktop/          - Electron + React frontend
jarvis/api.py            - FastAPI WebSocket bridge
jarvis/openclaw_bridge.py - Ultron/OpenClaw integration
```

---

## Setup
1. Clone repo
2. `cd JARVIS && python -m venv venv`
3. `venv\Scripts\activate`
4. `pip install -r requirements.txt`
5. Copy `.env.example` to `.env`, add your API keys
6. `python -m jarvis.cli` (terminal mode)

For Electron desktop:
7. `cd jarvis-desktop && npm install`
8. `npm run dev` (start Python `api.py` first)

---

## API Keys needed (.env)
```env
NVIDIA_NIM_API_KEY=
OPENWEATHER_API_KEY=
PICOVOICE_ACCESS_KEY= (optional, for wake word)
NEWSAPI_KEY= (optional, for global awareness)
```

---

## Created by
Nived — built in one session at age 20.
