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
from typing import Optional, AsyncGenerator, Callable
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
        self._initialize()
    
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
    
    async def speak_stream(self, text: str, sentence_callback: Optional[Callable] = None):
        """
        Stream TTS output sentence by sentence
        
        Args:
            text: Text to speak
            sentence_callback: Optional callback for each sentence
        """
        sentences = self._split_sentences(text)
        
        for sentence in sentences:
            if sentence_callback:
                sentence_callback(sentence)
            await self.speak(sentence)
    
def _clean_text_for_speech(text: str) -> str:
    """Clean markdown, code blocks, URLs, and rich tags for clear TTS vocalization"""
    if not text:
        return ""
    # Remove code blocks ```...```
    cleaned = re.sub(r'```[\s\S]*?```', ' code block omitted ', text)
    # Remove inline backticks `code`
    cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)
    # Remove markdown headers #, ##, etc.
    cleaned = re.sub(r'#+\s*', '', cleaned)
    # Remove URLs
    cleaned = re.sub(r'https?://\S+', '', cleaned)
    # Remove rich formatting tags like [bold cyan], [/bold cyan]
    cleaned = re.sub(r'\[/?[a-zA-Z0-9_:\s]+\]', '', cleaned)
    # Clean up whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


    async def speak(self, text: str):
        """
        Speak text using configured TTS engine
        
        Args:
            text: Text to speak
        """
        clean_text = _clean_text_for_speech(text)
        if not clean_text:
            return
        
        if self.engine_type == "edge":
            await self._speak_edge(clean_text)
        else:
            self._speak_pyttsx(clean_text)
    
    async def _speak_edge(self, text: str):
        """Speak using edge-tts"""
        try:
            communicate = edge_tts.Communicate(text, self.voice)
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_path = temp_file.name
            
            await communicate.save(temp_path)
            
            # Play using pygame
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
            
            self.pyttsx_engine.say(text)
            self.pyttsx_engine.runAndWait()
        except Exception as e:
            console.print(f"[red]Error with pyttsx3: {e}[/red]")
    
    def _play_audio(self, file_path: str):
        """Play audio file using pygame"""
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            
            # Run speaking animation for exact audio playback duration
            ui.animate_speaking(lambda: pygame.mixer.music.get_busy())
            
            pygame.mixer.music.unload()
                
        except Exception as e:
            console.print(f"[red]Error playing audio: {e}[/red]")
    
    async def speak_acknowledgment(self):
        """Speak a short acknowledgment phrase"""
        acknowledgments = ["On it.", "Working on it.", "Right away.", "Got it."]
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
        Speak a response using streaming TTS
        
        Args:
            text: Text to speak
        """
        if not self.enabled:
            return
        
        await self.tts.speak_stream(
            text,
            sentence_callback=self.response_callback
        )
    
    async def speak_acknowledgment(self):
        """Speak a short acknowledgment"""
        if self.enabled:
            await self.tts.speak_acknowledgment()


class ProactiveMonitor:
    """Background thread for proactive reminder monitoring"""
    
    def __init__(self, memory, tts_engine, check_interval: int = 60):
        """
        Initialize proactive monitor
        
        Args:
            memory: Memory instance for accessing reminders
            tts_engine: TTSEngine instance for speaking reminders
            check_interval: Seconds between reminder checks
        """
        self.memory = memory
        self.tts = tts_engine
        self.check_interval = check_interval
        self.running = False
        self.thread = None
        self.is_busy = False
        self.announcement_queue = []
        self.delivered_reminders = set()
    
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
        current_time = datetime.now()
        
        for reminder in reminders:
            if reminder["completed"]:
                continue
            
            reminder_id = reminder["id"]
            if reminder_id in self.delivered_reminders:
                continue
            
            # Check if reminder is due (has due_date and it's passed)
            due_date = reminder.get("due_date")
            if due_date:
                try:
                    due_datetime = datetime.fromisoformat(due_date)
                    if current_time >= due_datetime:
                        self._queue_announcement(reminder["text"])
                        self.delivered_reminders.add(reminder_id)
                        self.memory.complete_reminder(reminder_id)
                except ValueError:
                    pass
    
    def _queue_announcement(self, text: str):
        """Queue an announcement"""
        phrase = self._get_reminder_phrases(text)
        self.announcement_queue.append(phrase)
    
    def _deliver_announcements(self):
        """Deliver queued announcements when not busy"""
        while self.announcement_queue and not self.is_busy:
            phrase = self.announcement_queue.pop(0)
            try:
                # Speak the announcement
                asyncio.run(self.tts.speak(phrase))
            except Exception as e:
                console.print(f"[red]Error delivering announcement: {e}[/red]")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                self._check_reminders()
                self._deliver_announcements()
                time.sleep(self.check_interval)
            except Exception as e:
                console.print(f"[red]Monitor error: {e}[/red]")
                time.sleep(self.check_interval)
    
    def start(self):
        """Start the monitoring thread"""
        if self.running:
            return
        
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
    
    async def speak_boot_greeting(self, user_title: str = "sir"):
        """Speak boot greeting with status summary"""
        try:
            greeting = self._get_time_greeting()
            
            # Get status summary
            reminders = self.memory.get_reminders()
            pending_reminders = [r for r in reminders if not r["completed"]]
            tasks = self.memory.get_recent_tasks(5)
            
            status_parts = []
            if pending_reminders:
                status_parts.append(f"{len(pending_reminders)} reminders pending")
            if tasks:
                status_parts.append(f"{len(tasks)} recent tasks")
            
            if status_parts:
                status = ", ".join(status_parts)
                greeting_text = f"{greeting}, {user_title}. {status}."
            else:
                greeting_text = f"{greeting}, {user_title}. All systems nominal."
            
            await self.tts.speak(greeting_text)
            
        except Exception as e:
            console.print(f"[red]Error speaking boot greeting: {e}[/red]")
