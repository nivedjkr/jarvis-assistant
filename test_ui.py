"""
Test Sci-Fi HUD Terminal UI for JARVIS
"""
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("Testing JARVIS Sci-Fi HUD UI Components...\n")

from jarvis.ui import ui, UIState, COLOR_PRIMARY, PROMPT_SYMBOL

# Test 1: Color Constants
print("--- Test 1: Color & Style Constants ---")
print(f"✓ Primary Accent Color: {COLOR_PRIMARY}")
print(f"✓ Prompt Symbol: {PROMPT_SYMBOL}")

# Test 2: Status Badge Formatting
print("\n--- Test 2: Status Badge Formatting ---")
ui.set_state(UIState.IDLE)
badge_idle = ui.get_status_badge()
print(f"✓ IDLE status badge: {badge_idle}")

ui.set_state(UIState.THINKING)
badge_thinking = ui.get_status_badge()
print(f"✓ THINKING status badge: {badge_thinking}")

ui.set_state(UIState.EXECUTING)
badge_executing = ui.get_status_badge()
print(f"✓ EXECUTING status badge: {badge_executing}")

# Test 3: Boot Banner Rendering
print("\n--- Test 3: Rendering Startup Boot Banner ---")
ui.show_banner()

# Test 4: Response Panel Rendering
print("\n--- Test 4: Rendering Response Panel ---")
ui.render_response("Greetings, sir. All core tactical systems are fully operational.")

# Test 5: Tool Execution Rendering
print("\n--- Test 5: Tool Execution Rendering ---")
ui.render_tool_exec("Launching Visual Studio Code...", tag="EXEC")
ui.render_tool_exec("Executing Backup Protocol sequence...", tag="PROTOCOL")

print("\nAll Sci-Fi HUD UI tests PASSED successfully!")
