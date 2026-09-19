"""
Tests for Mark 5.5 Stark Workshop Upgrades:
- Sound Effects Engine (futuristic UI audio cues: wake, ack, done, alert)
- Hands-Free Wake-Word Detector (openWakeWord 'hey_jarvis', VAD, and barge-in interruption)
- CLI Slash Commands (/handsfree, /sound)
"""

import pytest
import asyncio
from pathlib import Path
from jarvis.sound_effects import play_sound, ensure_sound_files, SOUNDS_DIR
from jarvis.wake_word import WakeWordDetector
from jarvis.voice import VoiceManager
from jarvis.cli import JarvisAssistant


def test_sound_effects_files_and_playback():
    """Verify sound effect files exist and play_sound executes safely without error."""
    ensure_sound_files()
    assert SOUNDS_DIR.exists()
    for cue in ["wake", "ack", "done", "alert"]:
        file_path = SOUNDS_DIR / f"{cue}.wav"
        assert file_path.exists(), f"Missing audio cue file: {cue}.wav"
        assert file_path.stat().st_size > 0, f"Empty audio file: {cue}.wav"

    # Test non-blocking playback of all cues
    play_sound("wake", async_play=True)
    play_sound("ack", async_play=True)
    play_sound("done", async_play=True)
    play_sound("alert", async_play=True)


def test_wake_word_detector_lifecycle():
    """Verify WakeWordDetector initializes, tracks state, and handles start/stop."""
    barge_in_triggered = False

    def on_barge_in():
        nonlocal barge_in_triggered
        barge_in_triggered = True

    detector = WakeWordDetector(
        threshold=0.55,
        barge_in_callback=on_barge_in
    )
    assert detector.state == "IDLE"
    assert detector.threshold == 0.55
    assert not detector.running

    # Verify barge-in callback triggers
    detector.barge_in_callback()
    assert barge_in_triggered is True


def test_voice_manager_hands_free_methods():
    """Verify VoiceManager hands-free lifecycle methods and callbacks."""
    vm = VoiceManager({
        "enabled": False,
        "voice": {"speak_responses": True, "tts_engine": "edge"}
    })
    assert vm.wake_detector is None

    # Test enable/disable cycle
    vm.enable_hands_free()
    assert vm.wake_detector is not None
    assert vm.wake_detector.running is True

    vm.disable_hands_free()
    assert vm.wake_detector.running is False

    # Test barge-in stop speaking hook
    vm.stop_speaking()
    assert vm.is_speaking is False


@pytest.mark.asyncio
async def test_cli_handsfree_slash_commands():
    """Verify /handsfree and /sound slash commands in CLI."""
    app = JarvisAssistant()

    # 1. /sound command
    res_sound = await app.process("/sound wake")
    assert "Played Stark audio cue" in res_sound

    # 2. /handsfree status
    res_status = await app.process("/handsfree status")
    assert "Tony Stark Hands-Free Engine" in res_status

    # 3. /handsfree on
    res_on = await app.process("/handsfree on")
    assert "Tony Stark Hands-Free Mode ENABLED" in res_on

    # 4. /handsfree off
    res_off = await app.process("/handsfree off")
    assert "deactivated" in res_off.lower()
