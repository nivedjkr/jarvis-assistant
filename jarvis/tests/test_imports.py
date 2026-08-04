import sys

def test_imports():
    """Test that all primary JARVIS modules can be imported without errors."""
    import jarvis.cli
    import jarvis.api_client
    import jarvis.memory
    import jarvis.tools
    import jarvis.voice
    print("✓ All core modules imported successfully")

if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    print("Testing imports...")
    test_imports()
    print("\nAll imports completed!")
