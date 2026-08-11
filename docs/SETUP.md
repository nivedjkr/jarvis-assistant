# JARVIS Setup Guide

This guide provides step-by-step instructions to set up, configure, and run JARVIS on Windows.

## 1. Prerequisites
- Python 3.11+
- Node.js 18+ and npm (for Electron Desktop UI)
- GitHub CLI (`gh`) authenticated via `gh auth login`
- (Optional) Edge TTS / Pyttsx3 for voice playback

## 2. Environment Configuration
Copy `.env.example` to `.env` in the root directory:

```bash
cp .env.example .env
```

Edit `.env` and provide your API keys:
```env
JARVIS_LLM_PROVIDER=nvidia
NVIDIA_NIM_API_KEY=nvapi-your-key-here
GROQ_API_KEY=gsk_your_key_here
ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENWEATHER_API_KEY=your_openweather_key
```

## 3. Install Python Dependencies
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pydantic pytest pytest-asyncio httpx
```

## 4. Install Desktop UI Dependencies
```bash
cd jarvis-desktop
npm install
cd ..
```

## 5. Running JARVIS

### CLI Mode (Terminal)
```bash
python -m jarvis.cli
```

### Electron Desktop UI Mode
```bash
# Terminal 1: Launch Backend API Server
python -m jarvis.api

# Terminal 2: Launch Electron Frontend
cd jarvis-desktop
npm run dev
```

### Live Debug Dashboard
Launch in a side pane or dedicated terminal:
```bash
python -m jarvis.debug_panel
```

## 6. Running Tests
```bash
pytest jarvis/tests/ -v
```
