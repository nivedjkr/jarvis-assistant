---
name: cross-modal-vision
description: Multimodal visual inspection, UI layout debugging, screenshot analysis, and visual regression testing using meta/llama-3.2-11b-vision-instruct. Activate when inspecting screenshots, verifying frontend layouts, or analyzing images.
category: vision
---

# Cross-Modal Vision & Visual Debugging

Cross-modal vision extends the OBSERVE-REASON-ACT cycle to visual artifacts. Beyond textual assertions, visual verification ensures user interfaces, layouts, diagrams, and rendered screens function correctly.

## Core Capabilities

1. **Desktop Screen Inspection (`inspect_screen`)**:
   - Captures the primary display and executes vision-model inspection.
   - Automatically detects active application windows, error dialogs, visual glitches, and UI states.

2. **Targeted Image Analysis (`analyze_image`)**:
   - Inspects any image, chart, or screenshot saved on disk.
   - Ideal for analyzing Playwright screenshots (`browse_screenshot`) to verify that web applications render properly without broken CSS, misaligned flexboxes, or overlapping text.

## Visual Verification Workflow for Frontend / UI Tasks

1. Make frontend or layout code changes using `replace_file_content`.
2. Capture the rendered output using `browse_screenshot` (for web applications) or `inspect_screen` (for desktop UI).
3. Call `analyze_image` with a targeted query (e.g. *"Are the action buttons aligned and visible without overlapping text?"*).
4. Inspect the vision model's observations and apply surgical CSS/HTML corrections if visual regressions are identified.
