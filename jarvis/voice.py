"""
Voice I/O Module for JARVIS
Handles Speech-to-Text (STT) and Text-to-Speech (TTS)
"""

import asyncio
import queue
import threading
import tempfile
import os
import re
import time
from datetime import datetime
from typing import Optional, AsyncGenerator, Callable, Dict, Any, List, Tuple
from pathlib import Path

import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import edge_tts
import pyttsx3
import pygame
from pynput import keyboard
from rich.console import Console

from jarvis.ui import ui, UIState
from jarvis.system_monitor import SystemMonitor
from jarvis.weather import WeatherManager
from jarvis.google_auth import GoogleAuthManager
from jarvis.calendar_service import CalendarService
from jarvis.email_service import EmailService


console = Console()


class STTEngine:
    """Speech-to-Text engine using faster-whisper"""
    
    def __init__(self, model_size: str = "base", device: str = "cpu"):
        """
        Initialize STT engine
        
        Args:
            model_size: Model size ("base" or "small")
            device: Device to run on ("cpu" or "cuda")
        """
        self.model_size = model_size
        self.device = device
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the Whisper model"""
        try:
            console.print(f"[cyan]Loading STT model ({self.model_size})...[/cyan]")
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type="int8"
            )
            console.print("[green]STT model loaded successfully[/green]")
        except Exception as e:
            console.print(f"[red]Error loading STT model: {e}[/red]")
            self.model = None
    
    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        """
        Transcribe audio data to text
        
        Args:
            audio_data: NumPy array of audio samples
            sample_rate: Sample rate of audio
            
        Returns:
            Transcribed text
        """
        if self.model is None:
            return ""
        
        try:
            segments, info = self.model.transcribe(
                audio_data,
                language="en",
                beam_size=5
            )
            
            text = " ".join([segment.text for segment in segments])
            return text.strip()
        except Exception as e:
            console.print(f"[red]Error transcribing audio: {e}[/red]")
            return ""
    
    def transcribe_file(self, audio_file: str) -> str:
        """
        Transcribe audio file to text
        
        Args:
            audio_file: Path to audio file
            
        Returns:
            Transcribed text
        """
        if self.model is None:
            return ""
        
        try:
            segments, info = self.model.transcribe(
                audio_file,
                language="en",
                beam_size=5
            )
            
            text = " ".join([segment.text for segment in segments])
            return text.strip()
        except Exception as e:
            console.print(f"[red]Error transcribing file: {e}[/red]")
            return ""


def _clean_text_for_speech(text: str, speak_code_blocks: bool = False) -> str:
    """Clean markdown, code blocks, URLs, and rich tags for clear TTS vocalization"""
    if not text:
        return ""
    
    # Handle code blocks
    if not speak_code_blocks:
        cleaned = re.sub(r'```[\s\S]*?```', ' code block omitted ', text)
    else:
        cleaned = re.sub(r'```[a-zA-Z0-9_-]*\n?', ' ', text)
        cleaned = cleaned.replace('```', ' ')

    # Remove inline backticks `code`
    cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)
    # Remove markdown bold/italics
    cleaned = re.sub(r'[*_]{1,3}([^*_]+)[*_]{1,3}', r'\1', cleaned)
    # Remove markdown headers #, ##, etc.
    cleaned = re.sub(r'#+\s*', '', cleaned)
    # Remove URLs
    cleaned = re.sub(r'https?://\S+', '', cleaned)
    # Remove rich formatting tags like [bold cyan], [/bold cyan]
    cleaned = re.sub(r'\[/?[a-zA-Z0-9_:\s]+\]', '', cleaned)
    # Clean up whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Content filtering: If text is excessively long technical output (> 350 chars), summarize for speech
    if len(cleaned) > 350 and any(kw in cleaned.lower() for kw in ["file", "directory", "code", "output", "[dir]", "[file]", "path", "contents of"]):
        first_sentence = cleaned.split('.')[0] if '.' in cleaned else cleaned[:100]
        cleaned = f"{first_sentence}. Detailed response printed in terminal."

    return cleaned


class TTSEngine:
    """Text-to-Speech engine using edge-tts with pyttsx3 fallback"""
    
    def __init__(self, engine: str = "edge", voice: str = "en-GB-RyanNeural"):
        """
        Initialize TTS engine
        
        Args:
            engine: TTS engine ("edge" or "pyttsx3")
            voice: Voice name (for edge-tts)
        """
        self.engine_type = engine
        self.voice = voice
        self.pyttsx_engine = None
        self.is_cancelled = False
        self._is_speaking = False
        self._initialize()
    
    @property
    def is_speaking(self) -> bool:
        """Check if audio or TTS generation is currently active and not cancelled"""
        if self.is_cancelled:
            return False
        return self._is_speaking

    def stop_speaking(self):
        """Stop audio playback immediately and cancel remaining speech queue"""
        self.is_cancelled = True
        try:
            if pygame.mixer.get_init():
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
                try:
                    pygame.mixer.music.unload()
                except Exception:
                    pass
        except Exception as e:
            console.print(f"[dim yellow]Stop speaking warning: {e}[/dim yellow]")
        finally:
            self._is_speaking = False

    def _initialize(self):
        """Initialize the TTS engine"""
        if self.engine_type == "pyttsx3":
            try:
                self.pyttsx_engine = pyttsx3.init()
                console.print("[green]pyttsx3 TTS engine initialized[/green]")
            except Exception as e:
                console.print(f"[red]Error initializing pyttsx3: {e}[/red]")
                console.print("[yellow]Falling back to edge-tts[/yellow]")
                self.engine_type = "edge"
        else:
            console.print("[green]edge-tts TTS engine initialized[/green]")
    
    def _split_sentences(self, text: str) -> list:
        """
        Split text into sentences for streaming
        
        Args:
            text: Input text
            
        Returns:
            List of sentences
        """
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    async def speak_stream(self, text: str, sentence_callback: Optional[Callable] = None, speak_code_blocks: bool = False):
        """
        Stream TTS output sentence by sentence, checking cancellation between sentences
        
        Args:
            text: Text to speak
            sentence_callback: Optional callback for each sentence
            speak_code_blocks: Whether to speak code blocks aloud
        """
        self.is_cancelled = False
        sentences = self._split_sentences(text)
        
        for sentence in sentences:
            if self.is_cancelled:
                break
            if sentence_callback:
                try:
                    sentence_callback(sentence)
                except Exception:
                    pass
            await self.speak(sentence, speak_code_blocks=speak_code_blocks)
            if self.is_cancelled:
                break
    
    async def speak(self, text: str, speak_code_blocks: bool = False):
        """
        Speak text using configured TTS engine
        
        Args:
            text: Text to speak
            speak_code_blocks: Whether to speak code blocks aloud
        """
        if self.is_cancelled:
            return

        clean_text = _clean_text_for_speech(text, speak_code_blocks=speak_code_blocks)
        if not clean_text:
            return
        
        self._is_speaking = True
        try:
            if self.engine_type == "edge":
                await self._speak_edge(clean_text)
            else:
                self._speak_pyttsx(clean_text)
        except Exception as e:
            console.print(f"[dim yellow]TTS error: {e}[/dim yellow]")
        finally:
            self._is_speaking = False
    
    async def _speak_edge(self, text: str):
        """Speak using edge-tts"""
        try:
            communicate = edge_tts.Communicate(text, self.voice)
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_path = temp_file.name
            
            await communicate.save(temp_path)
            
            # Play using pygame
            if not self.is_cancelled:
                self._play_audio(temp_path)
            
            # Clean up
            os.unlink(temp_path)
            
        except Exception as e:
            console.print(f"[red]Error with edge-tts: {e}[/red]")
            console.print("[yellow]Trying pyttsx3 fallback...[/yellow]")
            self._speak_pyttsx(text)
    
    def _speak_pyttsx(self, text: str):
        """Speak using pyttsx3"""
        try:
            if self.pyttsx_engine is None:
                self.pyttsx_engine = pyttsx3.init()
            
            self._is_speaking = True
            self.pyttsx_engine.say(text)
            self.pyttsx_engine.runAndWait()
        except Exception as e:
            console.print(f"[red]Error with pyttsx3: {e}[/red]")
        finally:
            self._is_speaking = False
    
    def _play_audio(self, file_path: str):
        """Play audio file using pygame"""
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            self._is_speaking = True
            
            # Run speaking animation for exact audio playback duration unless cancelled
            while pygame.mixer.music.get_busy() and not self.is_cancelled:
                time.sleep(0.05)
                ui.animate_speaking(lambda: pygame.mixer.music.get_busy() and not self.is_cancelled)
            
            if self.is_cancelled and pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                
            pygame.mixer.music.unload()
                
        except Exception as e:
            console.print(f"[red]Error playing audio: {e}[/red]")
        finally:
            self._is_speaking = False
    
    async def speak_acknowledgment(self):
        """Speak a short acknowledgment phrase"""
        acknowledgments = [
            "On it, sir.",
            "Working on it, sir.",
            "Right away, sir.",
            "At your service, sir.",
            "Executing now, sir.",
            "Consider it done, sir.",
            "Processing request, sir."
        ]
        import random
        phrase = random.choice(acknowledgments)
        await self.speak(phrase)


class AudioRecorder:
    """Audio recorder using sounddevice"""
    
    def __init__(self, sample_rate: int = 16000, channels: int = 1, device: int = None):
        """
        Initialize audio recorder
        
        Args:
            sample_rate: Sample rate for recording
            channels: Number of audio channels
            device: Input device ID (None for default)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.recording = False
        self.audio_data = []
        self.stream = None
    
    def start_recording(self):
        """Start recording audio"""
        self.recording = True
        self.audio_data = []
        
        def callback(indata, frames, time, status):
            if status:
                console.print(f"[yellow]Recording status: {status}[/yellow]")
            if self.recording:
                self.audio_data.append(indata.copy())
        
        try:
            device_kwargs = {}
            if self.device is not None:
                device_kwargs['device'] = self.device
            
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=callback,
                **device_kwargs
            )
            console.print(f"[dim]Using device: {sd.query_devices(self.stream.device)['name']}[/dim]")
            self.stream.start()
        except Exception as e:
            console.print(f"[red]Error starting recording: {e}[/red]")
            self.recording = False
    
    def stop_recording(self) -> np.ndarray:
        """
        Stop recording and return audio data
        
        Returns:
            NumPy array of recorded audio
        """
        self.recording = False
        
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        if self.audio_data:
            audio = np.concatenate(self.audio_data, axis=0)
            # Flatten if stereo
            if audio.shape[1] > 1:
                audio = audio.mean(axis=1)
            return audio
        return np.array([])
    
    def is_recording(self) -> bool:
        """Check if currently recording"""
        return self.recording


class PushToTalkHandler:
    """Push-to-talk handler using keyboard input"""
    
    def __init__(self, key: str = "space"):
        """
        Initialize push-to-talk handler
        
        Args:
            key: Key to use for push-to-talk
        """
        self.key = key
        self.listener = None
        self.recording = False
        self.key_pressed = False  # Track if key is currently pressed
        self.on_press_callback = None
        self.on_release_callback = None
        self.listener_thread = None
        self.running = False
    
    def set_callbacks(self, on_press: Callable, on_release: Callable):
        """
        Set callbacks for key press/release
        
        Args:
            on_press: Callback when key is pressed
            on_release: Callback when key is released
        """
        self.on_press_callback = on_press
        self.on_release_callback = on_release
    
    def _on_press(self, key):
        """Handle key press"""
        try:
            if key == keyboard.Key.space or (hasattr(key, 'char') and key.char == self.key):
                if not self.key_pressed and self.on_press_callback:
                    self.key_pressed = True
                    self.on_press_callback()
        except AttributeError:
            pass
    
    def _on_release(self, key):
        """Handle key release"""
        try:
            if key == keyboard.Key.space or (hasattr(key, 'char') and key.char == self.key):
                if self.key_pressed and self.on_release_callback:
                    self.key_pressed = False
                    self.on_release_callback()
        except AttributeError:
            pass
    
    def start(self):
        """Start the keyboard listener"""
        if self.listener is not None:
            return
        
        self.running = True
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.start()
        console.print(f"[green]Push-to-talk enabled (hold {self.key} to record)[/green]")
    
    def stop(self):
        """Stop the keyboard listener"""
        self.running = False
        if self.listener:
            self.listener.stop()
            self.listener = None
            console.print("[yellow]Push-to-talk disabled[/yellow]")


class VoiceManager:
    """Main voice manager coordinating STT, TTS, and audio recording"""
    
    def __init__(self, config: dict):
        """
        Initialize voice manager
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.enabled = config.get("enabled", False)
        
        # Initialize components
        voice_config = config.get("voice", {})
        
        self.speak_responses = voice_config.get("speak_responses", True)
        self.speak_code_blocks = voice_config.get("speak_code_blocks", False)

        self.stt = STTEngine(
            model_size=voice_config.get("stt_model", "base"),
            device="cpu"
        )
        
        self.tts = TTSEngine(
            engine=voice_config.get("tts_engine", "edge"),
            voice=voice_config.get("tts_voice", "en-GB-RyanNeural")
        )
        
        self.recorder = AudioRecorder(
            device=voice_config.get("input_device", None)
        )
        
        self.ptt = PushToTalkHandler(
            key=voice_config.get("push_to_talk_key", "space")
        )
        
        self.transcription_callback = None
        self.response_callback = None
    
    @property
    def is_speaking(self) -> bool:
        """Check if TTS audio is actively playing"""
        return self.tts.is_speaking

    def stop_speaking(self):
        """Stop current speech playback immediately"""
        self.tts.stop_speaking()

    def set_callbacks(self, on_transcription: Callable, on_response: Callable):
        """
        Set callbacks for transcription and response
        
        Args:
            on_transcription: Callback when transcription is ready
            on_response: Callback when TTS speaks a sentence
        """
        self.transcription_callback = on_transcription
        self.response_callback = on_response
    
    def enable(self):
        """Enable voice mode"""
        self.enabled = True
        self.ptt.set_callbacks(
            on_press=self._on_ptt_press,
            on_release=self._on_ptt_release
        )
        self.ptt.start()
    
    def disable(self):
        """Disable voice mode"""
        self.enabled = False
        self.ptt.stop()
    
    def _on_ptt_press(self):
        """Handle push-to-talk press"""
        if not self.enabled:
            return
        
        ui.set_state(UIState.LISTENING)
        console.print("[cyan]🎤 Recording... (release to transcribe)[/cyan]")
        self.recorder.start_recording()
    
    def _on_ptt_release(self):
        """Handle push-to-talk release"""
        if not self.enabled:
            return
        
        audio_data = self.recorder.stop_recording()
        ui.set_state(UIState.THINKING)
        
        if len(audio_data) > 0:
            duration = len(audio_data) / 16000  # Duration in seconds
            console.print(f"[cyan]Processing audio ({duration:.2f}s)...[/cyan]")
            
            # Check audio levels
            audio_level = np.abs(audio_data).mean()
            max_level = np.abs(audio_data).max()
            console.print(f"[dim]Audio level: {audio_level:.4f} (max: {max_level:.4f})[/dim]")
            
            if audio_level < 0.001:
                console.print("[yellow]Audio too quiet - check microphone selection[/yellow]")
                console.print("[yellow]Run: python -c \"import sounddevice as sd; print(sd.query_devices())\"[/yellow]")
                return
            
            # Transcribe
            text = self.stt.transcribe(audio_data)
            
            if text:
                console.print(f"[yellow]Transcription:[/yellow] {text}")
                if self.transcription_callback:
                    self.transcription_callback(text)
            else:
                console.print("[yellow]No speech detected - try speaking more clearly[/yellow]")
        else:
            console.print("[yellow]No audio recorded[/yellow]")
    
    async def speak_response(self, text: str):
        """
        Speak a response using non-blocking/streaming TTS
        
        Args:
            text: Text to speak
        """
        if not self.speak_responses:
            return
        
        try:
            await self.tts.speak_stream(
                text,
                sentence_callback=self.response_callback,
                speak_code_blocks=self.speak_code_blocks
            )
        except Exception as e:
            console.print(f"[dim yellow]TTS warning: {e}[/dim yellow]")
    
    async def speak_acknowledgment(self):
        """Speak a short acknowledgment"""
        if self.enabled or self.speak_responses:
            await self.tts.speak_acknowledgment()


class ProactiveMonitor:
    """Background thread for proactive monitoring (reminders, system, weather, market, calendar, email)"""
    
    def __init__(self, memory, tts_engine, check_interval: int = 2, config: Optional[Dict[str, Any]] = None, api_client: Optional[Any] = None, project_manager: Optional[Any] = None):
        """
        Initialize proactive monitor
        """
        self.memory = memory
        self.tts = tts_engine
        self.check_interval = check_interval
        self.config = config or {}
        self.api_client = api_client
        if project_manager:
            self.project_manager = project_manager
        else:
            from jarvis.projects import ProjectManager
            self.project_manager = ProjectManager()

        self.running = False
        self.thread = None
        self.is_busy = False
        self._push_callback = None
        self.announcement_queue = []
        self.delivered_reminders = set()
        self.alerted_overdue_tasks = set()
        self.alerted_stale_projects = set()
        self.last_weekly_review_date = None
        self.last_check_timestamp: Optional[datetime] = None

        # Feature Managers
        self.system_monitor = SystemMonitor()
        self.weather_manager = WeatherManager(self.config)
        self.google_auth = GoogleAuthManager()
        self.calendar_service = CalendarService(self.google_auth)
        self.email_service = EmailService(self.google_auth, api_client=self.api_client)

        # Loop Timestamps
        now_ts = time.time()
        self._last_sys_check: float = now_ts
        self._last_price_check: float = now_ts
        self._last_weather_check: float = now_ts
        self._last_cal_check: float = now_ts
        self._last_email_check: float = now_ts
        self._last_project_check: float = now_ts
        self._last_github_check: float = 0.0
        self._boot_sys_alert_suppressed: bool = True

        # Rolling 10-minute price history: {ticker: [(timestamp, price)]}
        self._price_history: Dict[str, List[Tuple[float, float]]] = {}
        self._alerted_pct_windows: set = set()

    def set_push_callback(self, callback):
        """Set callback to push proactive alerts to external clients (e.g. Electron WebSocket)"""
        self._push_callback = callback

    def set_busy(self, busy: bool):
        """Set busy state (when JARVIS is mid-conversation/recording/speaking)"""
        self.is_busy = busy
    
    def _get_time_greeting(self):
        """Get time-appropriate greeting"""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "Good morning"
        elif 12 <= hour < 17:
            return "Good afternoon"
        else:
            return "Good evening"
    
    def _get_reminder_phrases(self, reminder_text: str):
        """Generate varied phrases for reminder announcements"""
        phrases = [
            f"Reminder: {reminder_text}",
            f"Just a heads up, {reminder_text}",
            f"Don't forget, {reminder_text}",
            f"Time to: {reminder_text}",
            f"Quick reminder about: {reminder_text}"
        ]
        import random
        return random.choice(phrases)
    
    def _check_reminders(self):
        """Check for due reminders"""
        reminders = self.memory.get_reminders()
        pending = [r for r in reminders if not r["completed"]]
        current_time = datetime.now()
        due_count = 0
        
        for reminder in pending:
            reminder_id = reminder["id"]
            if reminder_id in self.delivered_reminders:
                continue
            
            due_date = reminder.get("due_date")
            if due_date:
                try:
                    due_datetime = datetime.fromisoformat(due_date)
                    if current_time >= due_datetime:
                        due_count += 1
                        reminder_text = reminder["text"]
                        phrase = self._get_reminder_phrases(reminder_text)
                        
                        console.print(f"\n[bold bright_cyan]⏰ PROACTIVE REMINDER:[/bold bright_cyan] [bold white]{reminder_text}[/bold white]\n")
                        
                        self.delivered_reminders.add(reminder_id)
                        self.memory.complete_reminder(reminder_id)
                        self.announcement_queue.append(phrase)
                except ValueError:
                    pass

        now_str = current_time.strftime("%H:%M:%S")
        if pending or due_count > 0:
            console.print(f"[dim cyan][MONITOR {now_str}][/dim cyan] Checked {len(pending)} pending reminders ({due_count} due).", highlight=False)
    
    def _queue_announcement(self, text: str):
        """Queue an announcement"""
        self.announcement_queue.append(text)
    
    def _deliver_announcements(self):
        """Deliver queued announcements when not busy"""
        while self.announcement_queue and not self.is_busy:
            item = self.announcement_queue.pop(0)
            phrase = item[0] if isinstance(item, tuple) else item
            alert_type = item[1] if isinstance(item, tuple) else "reminder"

            pushed = False
            if self._push_callback:
                try:
                    import asyncio
                    import inspect
                    if inspect.iscoroutinefunction(self._push_callback):
                        pushed = bool(asyncio.run(self._push_callback(phrase, alert_type)))
                    else:
                        pushed = bool(self._push_callback(phrase, alert_type))
                except Exception as pe:
                    console.print(f"[dim yellow]Push alert error: {pe}[/dim yellow]")

            # Only invoke local Python TTS if NOT pushed to connected GUI frontend (prevents double sound)
            if not pushed:
                try:
                    if self.tts:
                        import asyncio
                        asyncio.run(self.tts.speak(phrase))
                except Exception as e:
                    console.print(f"[red]Error delivering announcement: {e}[/red]")
    
    def _check_deadlines(self):
        """Check for due deadlines and escalate alert frequency"""
        deadlines = self.memory.get_pending_deadlines()
        now = datetime.now()
        
        for d in deadlines:
            due_date_str = d.get("due_date")
            if not due_date_str:
                continue
            try:
                due_dt = datetime.fromisoformat(due_date_str)
                diff_hours = (due_dt - now).total_seconds() / 3600.0
                last_alerted_str = d.get("last_alerted")
                last_alerted = datetime.fromisoformat(last_alerted_str) if last_alerted_str else None
                
                should_alert = False
                alert_prefix = ""
                
                if 0 <= diff_hours <= 24:
                    if not last_alerted or (now - last_alerted).total_seconds() >= 10800:
                        should_alert = True
                        alert_prefix = f"URGENT DEADLINE IN {int(diff_hours)} HOURS:"
                elif 24 < diff_hours <= 72:
                    if not last_alerted or (now - last_alerted).total_seconds() >= 86400:
                        should_alert = True
                        alert_prefix = f"DEADLINE APPROACHING ({int(diff_hours / 24)} days away):"
                        
                if should_alert:
                    alert_text = f"{alert_prefix} {d['name']}"
                    console.print(f"\n[bold red]⚠️  {alert_text}[/bold red]\n")
                    self.memory.update_deadline_last_alerted(d["id"])
                    self.announcement_queue.append(alert_text)
            except ValueError:
                pass

    def _check_system_resources(self):
        """Check system resource thresholds every 30 seconds"""
        now_ts = time.time()
        if now_ts - self._last_sys_check < 30.0:
            return
        self._last_sys_check = now_ts

        try:
            alerts = self.system_monitor.evaluate_resource_anomalies()
            if self._boot_sys_alert_suppressed:
                # Suppress system resource alert popups/speech during the initial boot check
                self._boot_sys_alert_suppressed = False
                return

            for alert in alerts:
                console.print(f"\n[bold red]💻 SYSTEM MONITOR ALERT:[/bold red] [bold white]{alert['message']}[/bold white]\n")
                self.announcement_queue.append(alert["message"])
        except Exception as e:
            console.print(f"[dim yellow]System monitor evaluation warning: {e}[/dim yellow]")

    def _check_weather(self):
        """Check weather conditions every 30 minutes (1800s)"""
        now_ts = time.time()
        if now_ts - self._last_weather_check < 1800.0:
            return
        self._last_weather_check = now_ts

        try:
            alert = self.weather_manager.evaluate_weather_alerts()
            if alert:
                console.print(f"\n[bold cyan]🌧️ WEATHER ALERT:[/bold cyan] [bold white]{alert}[/bold white]\n")
                self.announcement_queue.append(alert)
        except Exception as e:
            console.print(f"[dim yellow]Weather monitor evaluation warning: {e}[/dim yellow]")

    def _fetch_ticker_news_summary(self, symbol: str) -> str:
        """Fetch recent headline context for a ticker using yfinance"""
        try:
            import yfinance as yf
            t = yf.Ticker(symbol)
            news = getattr(t, 'news', [])
            if news and isinstance(news, list):
                first = news[0]
                headline = first.get("title") or (first.get("content", {}).get("title") if isinstance(first.get("content"), dict) else None)
                if headline:
                    return headline.strip()
        except Exception:
            pass
        return ""

    def _check_price_watches(self):
        """Check active stock price watches every 30 seconds with rolling window % change and news context"""
        now_ts = time.time()
        if now_ts - self._last_price_check < 30.0:
            return
        self._last_price_check = now_ts

        watches = self.memory.get_active_price_watches()
        if not watches:
            return

        try:
            import yfinance as yf
            for w in watches:
                ticker = w["ticker"]
                condition = w["condition"].lower()
                target_price = float(w["target_price"])
                
                t = yf.Ticker(ticker)
                live_price = None
                if hasattr(t, 'fast_info') and 'lastPrice' in t.fast_info:
                    live_price = float(t.fast_info['lastPrice'])
                elif hasattr(t, 'info') and 'regularMarketPrice' in t.info and t.info.get('regularMarketPrice') is not None:
                    live_price = float(t.info.get('regularMarketPrice'))
                    
                if live_price is not None:
                    # Update rolling 10-minute history
                    if ticker not in self._price_history:
                        self._price_history[ticker] = []
                    self._price_history[ticker].append((now_ts, live_price))
                    # Prune history older than 10 mins (600s)
                    self._price_history[ticker] = [(ts, p) for ts, p in self._price_history[ticker] if now_ts - ts <= 600.0]

                    # 1. Check static threshold
                    triggered_static = False
                    if condition in ["above", ">", ">="] and live_price >= target_price:
                        triggered_static = True
                    elif condition in ["below", "<", "<="] and live_price <= target_price:
                        triggered_static = True

                    # 2. Check rolling window % change (>= 2%)
                    pct_move_str = ""
                    direction_str = ""
                    triggered_pct = False
                    if len(self._price_history[ticker]) >= 2:
                        first_ts, first_p = self._price_history[ticker][0]
                        if first_p > 0:
                            pct_change = ((live_price - first_p) / first_p) * 100.0
                            if abs(pct_change) >= 2.0:
                                direction_str = "up" if pct_change > 0 else "down"
                                pct_move_str = f"{direction_str} {abs(pct_change):.1f}% in the last 10 minutes"
                                window_key = (ticker, int(now_ts // 600))
                                if window_key not in self._alerted_pct_windows:
                                    self._alerted_pct_windows.add(window_key)
                                    triggered_pct = True

                    if triggered_static or triggered_pct:
                        news_headline = self._fetch_ticker_news_summary(ticker)
                        news_part = f" — recent headline: {news_headline}" if news_headline else ""
                        
                        if triggered_static and not pct_move_str:
                            direction = "up" if live_price >= target_price else "down"
                            alert_msg = f"{ticker} at ${live_price:.2f}, {direction} (crossed {condition} ${target_price:.2f}), sir{news_part}"
                        else:
                            alert_msg = f"{ticker} at ${live_price:.2f}, {pct_move_str}, sir{news_part}"

                        console.print(f"\n[bold bright_cyan]📈 MARKET ALERT:[/bold bright_cyan] [bold white]{alert_msg}[/bold white]\n")
                        if triggered_static:
                            self.memory.trigger_price_watch(w["id"])
                        self.announcement_queue.append(alert_msg)
        except Exception as e:
            console.print(f"[dim yellow]Market monitor check warning: {e}[/dim yellow]")

    def _check_calendar(self):
        """Check Google Calendar upcoming events every minute (60s)"""
        now_ts = time.time()
        if now_ts - self._last_cal_check < 60.0:
            return
        self._last_cal_check = now_ts

        try:
            alerts = self.calendar_service.evaluate_upcoming_alerts()
            for alert in alerts:
                console.print(f"\n[bold bright_cyan]📅 CALENDAR ALERT:[/bold bright_cyan] [bold white]{alert}[/bold white]\n")
                self.announcement_queue.append(alert)
        except Exception as e:
            console.print(f"[dim yellow]Calendar monitor evaluation warning: {e}[/dim yellow]")

    def _check_email(self):
        """Check Gmail inbox unread triage every 5 minutes (300s)"""
        now_ts = time.time()
        if now_ts - self._last_email_check < 300.0:
            return
        self._last_email_check = now_ts

        try:
            urgent_emails = self.email_service.evaluate_new_unread_emails()
            for item in urgent_emails:
                console.print(f"\n[bold bright_yellow]✉️  URGENT EMAIL:[/bold bright_yellow] [bold white]From: {item['sender']} — Subject: {item['subject']}[/bold white]\n")
                self.announcement_queue.append(item["spoken_phrase"])
        except Exception as e:
            console.print(f"[dim yellow]Email triage evaluation warning: {e}[/dim yellow]")

    def _check_projects(self):
        """Check active projects daily for overdue tasks, approaching deadlines, and stale activity"""
        now_ts = time.time()
        if now_ts - self._last_project_check < 600.0:
            return
        self._last_project_check = now_ts

        try:
            # 1. Overdue tasks alert
            overdue_tasks = self.project_manager.get_overdue_tasks()
            for t in overdue_tasks:
                task_id = t["id"]
                if task_id not in self.alerted_overdue_tasks:
                    self.alerted_overdue_tasks.add(task_id)
                    alert_text = f"Sir, task '{t['title']}' in '{t['project_name']}' is overdue since {t['due_date']}."
                    console.print(f"\n[bold red]⚠️ PROJECT OVERDUE TASK:[/bold red] [bold white]{alert_text}[/bold white]\n")
                    self.announcement_queue.append(alert_text)

            # 2. Approaching deadlines alert (within 7 days)
            approaching = self.project_manager.get_approaching_deadlines(7)
            for p in approaching:
                try:
                    deadline_dt = datetime.fromisoformat(p["deadline"])
                    days_left = (deadline_dt.date() - date.today()).days
                    if days_left >= 0:
                        alert_text = f"Sir, '{p['name']}' deadline is in {days_left} days."
                        console.print(f"\n[bold yellow]📅 PROJECT DEADLINE APPROACHING:[/bold yellow] [bold white]{alert_text}[/bold white]\n")
                except ValueError:
                    pass

            # 3. Stale projects alert (no updates in 14+ days)
            stale = self.project_manager.get_stale_projects(14)
            for p in stale:
                if p["id"] not in self.alerted_stale_projects:
                    self.alerted_stale_projects.add(p["id"])
                    alert_text = f"Sir, '{p['name']}' hasn't had any activity in 14 days. Still active?"
                    console.print(f"\n[bold cyan]💤 STALE PROJECT FLAG:[/bold cyan] [bold white]{alert_text}[/bold white]\n")

            # 4. Weekly Review on Mondays
            today = date.today()
            if today.weekday() == 0 and self.last_weekly_review_date != today:
                self.last_weekly_review_date = today
                res = self.project_manager.generate_weekly_project_review()
                spoken_summary = res["spoken_summary"]
                console.print(f"\n[bold bright_cyan]📊 WEEKLY PROJECT REVIEW:[/bold bright_cyan] [bold white]{spoken_summary}[/bold white]\n")
                self.announcement_queue.append(spoken_summary)
        except Exception as e:
            console.print(f"[dim yellow]Project monitor check warning: {e}[/dim yellow]")

    def _check_github(self):
        """Check GitHub for new issues, CI status changes, and new PRs"""
        now_ts = time.time()
        if now_ts - self._last_github_check < 1800.0:
            return
        self._last_github_check = now_ts

        try:
            import json
            from jarvis.github_tool import GitHubTool
            gh = GitHubTool()
            seen_file = Path("jarvis/data/github_seen.json")
            seen_file.parent.mkdir(parents=True, exist_ok=True)

            seen_data = {}
            if seen_file.exists():
                try:
                    with open(seen_file, "r", encoding="utf-8") as f:
                        seen_data = json.load(f)
                except Exception:
                    seen_data = {}

            for repo in gh.watch_repos:
                if repo not in seen_data or not isinstance(seen_data[repo], dict):
                    seen_data[repo] = {
                        "last_issue_number": 0,
                        "last_ci_conclusion": "success",
                        "last_pr_number": 0,
                        "last_checked": datetime.now().isoformat()
                    }
                
                state = seen_data[repo]
                first_time = (state.get("last_checked") is None) or (state.get("last_issue_number") == 0 and state.get("last_pr_number") == 0)

                # 1. Check issues
                issues_raw = gh._gh("issue", "list", "--repo", repo, "--state", "open", "--json", "number,title", as_json=True)
                if isinstance(issues_raw, list) and issues_raw:
                    latest_issue = max(issues_raw, key=lambda x: x.get("number", 0))
                    num = latest_issue.get("number", 0)
                    if num > state.get("last_issue_number", 0):
                        if not first_time and state.get("last_issue_number", 0) > 0:
                            alert_msg = f"Sir, new issue on {repo}: #{num} {latest_issue.get('title', '')}"
                            console.print(f"\n[bold bright_cyan]🐙 GITHUB ALERT:[/bold bright_cyan] [bold white]{alert_msg}[/bold white]\n")
                            self.announcement_queue.append(alert_msg)
                        state["last_issue_number"] = num

                # 2. Check PRs
                prs_raw = gh._gh("pr", "list", "--repo", repo, "--state", "open", "--json", "number,title", as_json=True)
                if isinstance(prs_raw, list) and prs_raw:
                    latest_pr = max(prs_raw, key=lambda x: x.get("number", 0))
                    num = latest_pr.get("number", 0)
                    if num > state.get("last_pr_number", 0):
                        if not first_time and state.get("last_pr_number", 0) > 0:
                            alert_msg = f"Sir, new PR on {repo}: #{num} {latest_pr.get('title', '')}"
                            console.print(f"\n[bold bright_cyan]🐙 GITHUB ALERT:[/bold bright_cyan] [bold white]{alert_msg}[/bold white]\n")
                            self.announcement_queue.append(alert_msg)
                        state["last_pr_number"] = num

                # 3. Check CI
                runs_raw = gh._gh("run", "list", "--repo", repo, "--limit", "1", "--json", "status,conclusion,name", as_json=True)
                if isinstance(runs_raw, list) and runs_raw:
                    latest_run = runs_raw[0]
                    curr_conc = latest_run.get("conclusion") or latest_run.get("status") or "unknown"
                    last_conc = state.get("last_ci_conclusion", "success")
                    if curr_conc != last_conc:
                        if curr_conc == "failure":
                            alert_msg = f"Sir, CI failed on {repo}"
                            console.print(f"\n[bold red]🐙 GITHUB CI ALERT:[/bold red] [bold white]{alert_msg}[/bold white]\n")
                            self.announcement_queue.append(alert_msg)
                        elif curr_conc == "success" and last_conc == "failure":
                            alert_msg = f"Sir, CI is passing again on {repo}"
                            console.print(f"\n[bold green]🐙 GITHUB CI ALERT:[/bold green] [bold white]{alert_msg}[/bold white]\n")
                            self.announcement_queue.append(alert_msg)
                        state["last_ci_conclusion"] = curr_conc

                state["last_checked"] = datetime.now().isoformat()

            with open(seen_file, "w", encoding="utf-8") as f:
                json.dump(seen_data, f, indent=2)

        except Exception as e:
            console.print(f"[dim yellow]GitHub monitor check warning: {e}[/dim yellow]")

    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                self.last_check_timestamp = datetime.now()
                self._check_reminders()
                self._check_deadlines()
                self._check_system_resources()
                self._check_weather()
                self._check_price_watches()
                self._check_calendar()
                self._check_email()
                self._check_projects()
                self._check_github()
                self._deliver_announcements()
                time.sleep(self.check_interval)
            except Exception as e:
                console.print(f"[red]Monitor error: {e}[/red]")
                time.sleep(self.check_interval)
    
    def start(self):
        """Start the monitoring thread"""
        if self.running:
            return
        
        now_ts = time.time()
        self._last_sys_check = now_ts
        self._last_price_check = now_ts
        self._last_weather_check = now_ts
        self._last_cal_check = now_ts
        self._last_email_check = now_ts
        self._boot_sys_alert_suppressed = True

        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        console.print("[dim]Proactive monitor started[/dim]")
    
    def stop(self):
        """Stop the monitoring thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
        console.print("[dim]Proactive monitor stopped[/dim]")
    
    def get_boot_greeting(self, user_title: str = "sir") -> str:
        """Get boot greeting text enriched with real calendar event count and randomized status phrases"""
        try:
            greeting = self._get_time_greeting()
            
            # Real calendar summary
            cal_summary = self.calendar_service.get_today_summary()
            cal_phrase = f" {cal_summary}" if cal_summary else ""

            import random
            random_closings = [
                "At your service, sir.",
                "Standing by for instructions.",
                "All systems operational and ready.",
                "Ready for your command.",
                "At your service.",
                "Online and ready for your command.",
                "All systems nominal and standing by."
            ]
            closing = random.choice(random_closings)

            return f"{greeting}, {user_title}.{cal_phrase} {closing}".strip()
        except Exception:
            return f"Good day, {user_title}. JARVIS online and standing by."

    async def speak_boot_greeting(self, user_title: str = "sir"):
        """Speak boot greeting enriched with real calendar event count and randomized status phrases"""
        try:
            greeting_text = self.get_boot_greeting(user_title)
            
            from jarvis.ui import ui
            ui.render_response(greeting_text)
            await self.tts.speak(greeting_text)
            
        except Exception as e:
            console.print(f"[red]Error speaking boot greeting: {e}[/red]")


async def test_tts() -> tuple[bool, str]:
    """Check if edge-tts can generate audio clips"""
    try:
        import edge_tts
        communicate = edge_tts.Communicate("test", "en-US-SteffanNeural")
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
        if len(audio_bytes) > 0:
            return True, f"edge-tts online ({len(audio_bytes)} audio bytes generated)"
        return False, "edge-tts returned 0 audio bytes"
    except Exception as e:
        return False, f"TTS clip generation error: {e}"


def test_mic() -> tuple[bool, str]:
    """Check if configured audio input device is detected"""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devices = [d for d in devices if d.get('max_input_channels', 0) > 0]
        if not input_devices:
            return False, "no input device detected"
        try:
            default_in = sd.query_devices(kind='input')
            dev_name = default_in.get('name', input_devices[0]['name'])
            return True, f"Detected: {dev_name}"
        except Exception:
            return True, f"Detected: {input_devices[0]['name']}"
    except Exception as e:
        return False, f"Mic detection error: {e}"
