"""
WakeWordDetector for JARVIS (Mark 5.5 Hands-Free Stark Architecture)
Continuous open-microphone wake-word detection using openWakeWord ('hey_jarvis'),
energy-based Voice Activity Detection (VAD), automated barge-in speech interruption,
and seamless handoff to speech-to-text transcription.
"""

import time
import math
import threading
import numpy as np
from typing import Optional, Callable, Any
from jarvis.sound_effects import play_sound


class WakeWordDetector:
    """
    Background worker listening for 'hey jarvis' on the microphone,
    triggering audio cues, barge-in interruption, and speech capture.
    """

    def __init__(
        self,
        threshold: float = 0.5,
        sample_rate: int = 16000,
        chunk_samples: int = 1280,
        on_wake: Optional[Callable[[], None]] = None,
        on_command: Optional[Callable[[str], None]] = None,
        barge_in_callback: Optional[Callable[[], None]] = None,
        stt_engine: Optional[Any] = None
    ):
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.chunk_samples = chunk_samples
        self.on_wake = on_wake
        self.on_command = on_command
        self.barge_in_callback = barge_in_callback
        self.stt_engine = stt_engine

        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._model = None
        self.state = "IDLE"  # IDLE, RECORDING
        self._speech_buffer = []
        self._silence_frames = 0
        self._max_silence_frames = int(1.4 * (sample_rate / chunk_samples))  # ~1.4s silence
        self._speech_detected = False

    def _load_model(self):
        if self._model is None:
            from openwakeword.model import Model
            self._model = Model(wakeword_models=["hey_jarvis"])

    def start(self):
        """Starts background hands-free listening loop."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True, name="WakeWordListener")
        self._thread.start()
        print("[WAKE] Hands-free wake-word detector activated ('Hey JARVIS')")

    def stop(self):
        """Stops background listening loop."""
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self.state = "IDLE"
        print("[WAKE] Hands-free wake-word detector stopped.")

    def _compute_rms(self, audio_chunk: np.ndarray) -> float:
        if len(audio_chunk) == 0:
            return 0.0
        return float(np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)))

    def _listen_loop(self):
        """Streaming audio loop consuming microphone blocks."""
        try:
            self._load_model()
        except Exception as e:
            print(f"[WAKE] Failed to initialize wake word model: {e}")
            self.running = False
            return

        try:
            import sounddevice as sd
        except ImportError:
            print("[WAKE] sounddevice not available. Wake word disabled.")
            self.running = False
            return

        while self.running:
            try:
                with sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype='int16',
                    blocksize=self.chunk_samples
                ) as stream:
                    while self.running:
                        audio_chunk, overflow = stream.read(self.chunk_samples)
                        if overflow:
                            continue

                        flat_chunk = audio_chunk.flatten()

                        if self.state == "IDLE":
                            # Predict wake word score
                            prediction = self._model.predict(flat_chunk)
                            score = prediction.get("hey_jarvis", 0.0)

                            if score >= self.threshold:
                                print(f"[WAKE] Wake word detected! Score: {score:.3f}")
                                # 1. Trigger barge-in immediately
                                if self.barge_in_callback and callable(self.barge_in_callback):
                                    try:
                                        self.barge_in_callback()
                                    except Exception:
                                        pass

                                # 2. Play Stark wake sound
                                play_sound("wake")

                                # 3. Notify callback (e.g. UI state to LISTENING)
                                if self.on_wake and callable(self.on_wake):
                                    try:
                                        self.on_wake()
                                    except Exception:
                                        pass

                                # 4. Switch to recording user command
                                self.state = "RECORDING"
                                self._speech_buffer = []
                                self._silence_frames = 0
                                self._speech_detected = False

                        elif self.state == "RECORDING":
                            self._speech_buffer.append(flat_chunk)
                            rms = self._compute_rms(flat_chunk)

                            # Energy-based speech activity detection
                            if rms > 450:  # Active speech threshold
                                self._speech_detected = True
                                self._silence_frames = 0
                            else:
                                if self._speech_detected:
                                    self._silence_frames += 1

                            # End of speech condition (silence detected after speech, or max 12 seconds)
                            max_buffer_chunks = int(12.0 * (self.sample_rate / self.chunk_samples))
                            if (self._speech_detected and self._silence_frames >= self._max_silence_frames) or len(self._speech_buffer) >= max_buffer_chunks:
                                self.state = "IDLE"
                                recorded_audio = np.concatenate(self._speech_buffer)
                                self._speech_buffer = []
                                self._silence_frames = 0
                                self._speech_detected = False

                                # Play acknowledge chime
                                play_sound("ack")

                                # Transcribe and dispatch in a separate thread so audio loop never blocks
                                threading.Thread(
                                    target=self._process_recorded_audio,
                                    args=(recorded_audio,),
                                    daemon=True
                                ).start()

            except Exception as e:
                if self.running:
                    print(f"[WAKE] Audio stream warning: {e}. Retrying in 2 seconds...")
                    time.sleep(2.0)

    def _process_recorded_audio(self, audio_data: np.ndarray):
        """Transcribes audio using STTEngine and triggers on_command callback."""
        if self.stt_engine is None:
            try:
                from jarvis.voice import STTEngine
                self.stt_engine = STTEngine(model_size="base", device="cpu")
            except Exception as e:
                print(f"[WAKE] Could not load STT engine: {e}")
                return

        # Normalize int16 numpy array to float32 between -1.0 and 1.0 for Whisper
        audio_float = audio_data.astype(np.float32) / 32768.0
        try:
            text = self.stt_engine.transcribe(audio_float, sample_rate=self.sample_rate)
            text_clean = (text or "").strip()
            if text_clean:
                print(f"[WAKE] User Spoke: \"{text_clean}\"")
                if self.on_command and callable(self.on_command):
                    self.on_command(text_clean)
            else:
                print("[WAKE] Empty transcription or background noise.")
        except Exception as e:
            print(f"[WAKE] Transcription error: {e}")
