"""
Test Robust TTS Interrupt Handling & State Tracking for JARVIS
"""
import sys
import asyncio
import time
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Testing JARVIS TTS Interrupt Handling & State Tracking...\n")

from jarvis.cli import JARVISCLI

cli = JARVISCLI()
vm = cli.voice_manager

async def run_interrupt_tests():
    # Test 1: Initial state
    print("--- Test 1: Initial Speaking State ---")
    print(f"✓ Initial is_speaking: {vm.is_speaking}")
    assert vm.is_speaking is False

    # Test 2: Background playback interruption
    print("\n--- Test 2: Rapid Interruption during Speech ---")
    long_speech_text = (
        "This is sentence number one of a long speech test. "
        "This is sentence number two which should be interrupted before completion. "
        "This is sentence number three which should never play at all."
    )
    
    # Start long speech in background
    task1 = asyncio.create_task(vm.speak_response(long_speech_text))
    await asyncio.sleep(0.3)  # Allow audio to start
    
    print(f"✓ is_speaking during active playback: {vm.is_speaking}")
    
    # Trigger interruption via cli.stop_speech()
    cli.stop_speech()
    await asyncio.sleep(0.1)
    
    print(f"✓ is_speaking after stop_speech(): {vm.is_speaking}")
    assert vm.is_speaking is False

    # Test 3: Audio overlap prevention & new message transition
    print("\n--- Test 3: Rapid consecutive messages (No Overlap) ---")
    task2 = asyncio.create_task(vm.speak_response("First response sentence."))
    cli.stop_speech()
    
    task3 = asyncio.create_task(vm.speak_response("Second response sentence immediately following interrupt."))
    await asyncio.sleep(0.2)
    cli.stop_speech()
    await asyncio.sleep(0.1)
    
    print(f"✓ Final is_speaking state after rapid interrupts: {vm.is_speaking}")
    assert vm.is_speaking is False

asyncio.run(run_interrupt_tests())

print("\nAll Interrupt Handling & State Tracking tests PASSED successfully!")
