"""
Sound Effects Engine for JARVIS (Mark 5.5 Stark Audio Architecture)
Provides zero-latency futuristic UI audio cues (wake, ack, done, alert)
using native asynchronous Windows audio with fallback to sounddevice.
"""

import os
import sys
import threading
from pathlib import Path
from typing import Optional

SOUNDS_DIR = Path(__file__).parent / "data" / "sounds"


def ensure_sound_files():
    """Synthesizes high-fidelity futuristic Stark audio tones if not already present."""
    SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
    required = ["wake.wav", "ack.wav", "done.wav", "alert.wav"]
    if all((SOUNDS_DIR / f).exists() for f in required):
        return

    try:
        import numpy as np
        from scipy.io import wavfile
        sample_rate = 44100

        def _make_tone(filename, freqs, durations, decay=6.0):
            full_audio = []
            for f, d in zip(freqs, durations):
                t = np.linspace(0, d, int(sample_rate * d), endpoint=False)
                env = np.exp(-decay * t)
                wave = 0.5 * np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * f * 2 * t)
                full_audio.append(wave * env)
            audio = np.concatenate(full_audio)
            audio_int16 = (audio * 32767).astype(np.int16)
            wavfile.write(str(SOUNDS_DIR / filename), sample_rate, audio_int16)

        # 1. Wake: Futuristic upward Stark chime (880Hz -> 1760Hz)
        _make_tone('wake.wav', [880, 1760], [0.08, 0.25], decay=8.0)
        # 2. Ack: Low subtle confirmation resonance (523Hz -> 659Hz)
        _make_tone('ack.wav', [523.25, 659.25], [0.06, 0.18], decay=7.0)
        # 3. Done: High-tech completion triad (659Hz -> 880Hz -> 1318Hz)
        _make_tone('done.wav', [659.25, 880.0, 1318.5], [0.07, 0.07, 0.3], decay=6.0)
        # 4. Alert: Double descending alert pulse (440Hz -> 370Hz)
        _make_tone('alert.wav', [440, 370], [0.12, 0.25], decay=9.0)
    except Exception as e:
        print(f"[SOUND] Warning: Could not synthesize audio files: {e}")


def play_sound(name: str, async_play: bool = True):
    """
    Plays a named Stark UI audio cue ('wake', 'ack', 'done', 'alert').
    Executes asynchronously with zero blocking on the main thread.
    """
    ensure_sound_files()
    clean_name = name.lower().replace(".wav", "")
    target_file = SOUNDS_DIR / f"{clean_name}.wav"
    if not target_file.exists():
        return

    sound_path = str(target_file.resolve())

    if sys.platform == "win32":
        try:
            import winsound
            flags = winsound.SND_FILENAME
            if async_play:
                flags |= winsound.SND_ASYNC | winsound.SND_NODEFAULT
            winsound.PlaySound(sound_path, flags)
            return
        except Exception:
            pass

    # Fallback for non-Windows or if winsound fails
    def _play_thread():
        try:
            import sounddevice as sd
            from scipy.io import wavfile
            sr, data = wavfile.read(sound_path)
            sd.play(data, sr)
            sd.wait()
        except Exception:
            pass

    if async_play:
        threading.Thread(target=_play_thread, daemon=True).start()
    else:
        _play_thread()


# Ensure files exist upon module import
ensure_sound_files()
