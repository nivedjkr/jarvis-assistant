import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Testing imports...")

try:
    import jarvis.cli
    print("✓ jarvis.cli imported")
except Exception as e:
    print(f"✗ jarvis.cli failed: {e}")

try:
    import jarvis.api_client
    print("✓ jarvis.api_client imported")
except Exception as e:
    print(f"✗ jarvis.api_client failed: {e}")

try:
    import jarvis.memory
    print("✓ jarvis.memory imported")
except Exception as e:
    print(f"✗ jarvis.memory failed: {e}")

try:
    import jarvis.tools
    print("✓ jarvis.tools imported")
except Exception as e:
    print(f"✗ jarvis.tools failed: {e}")

try:
    import jarvis.voice
    print("✓ jarvis.voice imported")
except Exception as e:
    print(f"✗ jarvis.voice failed: {e}")

print("\nAll imports completed!")
