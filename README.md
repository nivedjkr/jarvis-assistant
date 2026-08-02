# JARVIS - Your Terminal AI Assistant

A powerful CLI-based AI assistant that runs in your terminal, powered by NVIDIA NIM API. JARVIS can help you with file operations, system commands, and general tasks through natural language.

## Features

- 🤖 **AI-Powered**: Uses NVIDIA NIM API with Llama 3.1 405B model
- 💬 **Interactive Chat**: Natural conversation with streaming responses
- 🎙️ **Voice Mode**: Speech-to-text and text-to-speech for hands-free interaction
- 🛠️ **Tool System**: File operations, shell commands, directory management
- 📝 **Memory System**: Reminders, notes, and task history
- 🎨 **Beautiful UI**: Rich terminal formatting with colors and panels
- 🔒 **Safe Operations**: Confirmation prompts for dangerous commands
- 📊 **Command Logging**: All commands logged for safety and audit

## Installation

### Prerequisites

- Python 3.8 or higher
- NVIDIA NIM API key (free from [build.nvidia.com](https://build.nvidia.com/))

### Setup

1. **Clone or download the project**

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**

   Windows:
   ```bash
   venv\Scripts\activate
   ```

   Linux/Mac:
   ```bash
   source venv/bin/activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Set up your API key**

   Copy `.env.example` to `.env`:
   ```bash
   copy .env.example .env
   ```

   Edit `.env` and add your NVIDIA NIM API key:
   ```
   NVIDIA_NIM_API_KEY=your_actual_api_key_here
   ```

## Usage

### Start JARVIS

```bash
python -m jarvis.cli
```

Or directly:
```bash
python jarvis/cli.py
```

### Available Commands

#### Slash Commands

- `/help` - Show help message
- `/clear` - Clear the screen
- `/exit` - Exit JARVIS
- `/history` - Show conversation history
- `/tools` - List available tools
- `/reminders` - Show your reminders
- `/notes` - Show your notes
- `/tasks` - Show recent task history
- `/voice on` - Enable voice mode (push-to-talk)
- `/voice off` - Disable voice mode

#### Natural Language Commands

- "Create a folder called X" - Create directory
- "Read file X" - Read file contents
- "List files in X" - List directory contents
- "Search for X" - Search for files
- "Run command X" - Execute shell command
- "Remind me to X" - Add a reminder
- "Note: X" - Add a note

#### Examples

```
You: Create a folder called my_project
JARVIS: Created directory: my_project

You: Read file README.md
JARVIS: Contents of README.md: ...

You: List files in .
JARVIS: [DIR] jarvis
[FILE] README.md
[FILE] requirements.txt

You: Run command dir
JARVIS: (directory listing)

You: Remind me to update the documentation
JARVIS: Reminder added: to update the documentation

You: Note: Remember to check the logs
JARVIS: Note saved: Remember to check the logs
```

## Configuration

Edit `config.yaml` to customize JARVIS:

```yaml
api:
  base_url: "https://integrate.api.nvidia.com/v1"
  model: "meta/llama-3.1-405b-instruct"
  temperature: 0.7
  max_tokens: 1000
  stream: true

memory:
  file: "jarvis_memory.json"
  log_file: "jarvis_commands.log"

tools:
  confirm_dangerous: true
  log_commands: true

voice:
  enabled: false
  stt_model: "base"  # "base" or "small" for faster-whisper
  tts_engine: "edge"  # "edge" or "pyttsx3"
  tts_voice: "en-GB-RyanNeural"  # Edge TTS voice
  push_to_talk_key: "space"  # Key for push-to-talk
  wake_word_enabled: false  # Enable wake word detection
  silence_threshold: 0.5  # Silence detection threshold (0-1)
  auto_stop_recording: true  # Auto-stop on silence
```

### Available NVIDIA NIM Models

- `meta/llama-3.1-8b-instruct` (default, most available)
- `meta/llama-3.1-70b-instruct`
- `mistralai/mistral-large`
- `google/gemma-7b`

## Project Structure

```
JARVIS/
├── jarvis/
│   ├── __init__.py
│   ├── cli.py           # Main CLI application
│   ├── api_client.py    # NVIDIA NIM API client
│   ├── tools.py         # Tool system and implementations
│   ├── memory.py        # Memory and logging system
│   └── voice.py         # Voice I/O (STT/TTS) module
├── config.yaml          # Configuration file
├── requirements.txt     # Python dependencies
├── .env.example        # Environment variables template
└── README.md           # This file
```

## Safety Features

- **Confirmation Prompts**: Dangerous commands require user confirmation
- **Command Logging**: All executed commands are logged to `jarvis_commands.log`
- **Memory Persistence**: Reminders, notes, and task history saved across sessions
- **Error Handling**: Graceful error handling with clear messages

## Adding Custom Tools

To add a new tool, create a class inheriting from `Tool` in `tools.py`:

```python
class MyCustomTool(Tool):
    def __init__(self):
        super().__init__("my_tool", "Description of my tool")
    
    async def execute(self, **kwargs) -> str:
        # Your tool logic here
        return "Result"
```

Then register it in the `ToolRegistry`:

```python
self.register(MyCustomTool())
```

## Voice Mode

JARVIS now supports voice interaction for an Iron-Man-style experience!

### Enabling Voice Mode

1. Type `/voice on` to enable voice mode
2. Hold the **spacebar** to record your voice
3. Release to transcribe and send to JARVIS
4. JARVIS will respond both visually and with speech
5. Type `/voice off` to disable voice mode

### Voice Features

- **Speech-to-Text**: Uses `faster-whisper` for accurate transcription
- **Text-to-Speech**: Uses `edge-tts` for natural-sounding speech
- **Push-to-Talk**: Hold spacebar to record (configurable)
- **Streaming TTS**: Speaks responses as they're generated
- **Mixed Input**: Type or talk - both work in voice mode

### Voice Configuration

Edit `config.yaml` to customize voice settings:

- `stt_model`: "base" (faster) or "small" (more accurate)
- `tts_engine`: "edge" (online, better quality) or "pyttsx3" (offline)
- `tts_voice`: Edge TTS voice name (e.g., "en-GB-RyanNeural")
- `push_to_talk_key`: Key for push-to-talk (default: space)

### Troubleshooting Voice Issues

**Microphone not working:**
- Ensure your microphone is connected and recognized by your system
- Check that no other application is using the microphone
- Try running with administrator privileges

**STT errors:**
- First run will download the Whisper model (may take a few minutes)
- Ensure you have enough disk space (~150MB for base model)
- Try switching between "base" and "small" models

**TTS not speaking:**
- Check your internet connection (edge-tts requires internet)
- If offline, switch `tts_engine` to "pyttsx3" in config.yaml
- Ensure your system audio is working

**Keyboard listener issues:**
- On Windows, may need administrator privileges
- On Linux, may need to add user to input group
- Try a different key in config.yaml if spacebar doesn't work

## Troubleshooting

### API Key Issues

If you get an error about the API key:
1. Ensure you've set `NVIDIA_NIM_API_KEY` in your `.env` file
2. Make sure the `.env` file is in the same directory as `cli.py`
3. Verify your API key is valid at [build.nvidia.com](https://build.nvidia.com/)

### Import Errors

If you get import errors:
1. Make sure you've activated your virtual environment
2. Run `pip install -r requirements.txt` again
3. Ensure you're running from the project root directory

### Model Errors

If the model fails to respond or you get a 404 error:
1. Check your internet connection
2. Verify the model name in `config.yaml` is correct
3. Try switching to a different model:
   - `meta/llama-3.1-8b-instruct` (recommended)
   - `meta/llama-3.1-70b-instruct`
   - `mistralai/mistral-large`
4. Check if your API key has access to the model at [build.nvidia.com](https://build.nvidia.com/)
5. Verify the API endpoint is correct: `https://integrate.api.nvidia.com/v1`

## License

MIT License - Feel free to use and modify as needed.

## Contributing

Contributions are welcome! Feel free to submit issues or pull requests.

---

**Built with ❤️ using NVIDIA NIM API**
