"""
Automated Ground-Truth Verification for Student Features Phase 1
"""
import sys
import os
import asyncio
from datetime import datetime, timedelta
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path

root_dir = str(Path(__file__).resolve().parent.parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

print("Testing Student Features (Phase 1)...\n")

from jarvis.cli import JARVISCLI

cli = JARVISCLI()

async def run_student_tests():
    # -------------------------------------------------------------
    # 1. Flashcard System
    # -------------------------------------------------------------
    print("--- 1.1 Flashcard System: Add & Storage ---")
    card_res = await cli.process_command('/flashcard add "What is the capital of France?" "Paris"')
    print(f"✓ Output:\n{card_res}\n")
    assert "Paris" in card_res

    # Flashcards from file
    notes_file = "sample_notes.txt"
    with open(notes_file, "w", encoding="utf-8") as f:
        f.write("Q: What is H2O? A: Water.\nQ: What is speed of light? A: 300000 km/s.")
    
    try:
        from_file_res = await cli.process_command(f"/flashcard from-file {notes_file}")
        print(f"✓ Output:\n{from_file_res}\n")
        assert "Extracted and stored" in from_file_res or "flashcards" in from_file_res.lower()

        due_cards = cli.memory.get_due_flashcards()
        print(f"✓ Due flashcards count in SQLite: {len(due_cards)}")
        assert len(due_cards) >= 1

        # Spaced repetition interval update
        card_id = due_cards[0]["id"]
        cli.memory.update_flashcard_review(card_id, correct=True)
        print(f"✓ Updated spaced repetition interval for Card #{card_id}")
    finally:
        if os.path.exists(notes_file):
            os.remove(notes_file)

    # -------------------------------------------------------------
    # 2. Deadline Tracker & Proactive Monitor Escalation
    # -------------------------------------------------------------
    print("\n--- 1.2 Deadline Tracker & Proactive Escalation ---")
    deadline_res = await cli.process_command('/deadline add "CS101 Final Project" in 2 days')
    print(f"✓ Output:\n{deadline_res}\n")
    assert "CS101 Final Project" in deadline_res

    deadlines_summary = cli.show_deadlines()
    print(f"✓ Deadlines List:\n{deadlines_summary}\n")
    assert "CS101 Final Project" in deadlines_summary

    # Trigger proactive deadline monitor check
    cli.proactive_monitor._check_deadlines()
    print("✓ Proactive monitor deadline check executed successfully.")

    # -------------------------------------------------------------
    # 3. PDF Summarizer Tool
    # -------------------------------------------------------------
    print("\n--- 1.3 PDF Summarizer Tool ---")
    pdf_path = "test_paper.pdf"
    
    # Write valid PDF with real text content
    pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/Resources<</Font<</F1<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>>>>>/Contents 4 0 R>>endobj 4 0 obj<</Length 100>>stream\nBT /F1 12 Tf 100 700 Td (CLAIM: Multi-agent AI systems outperform single agents.) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000111 00000 n\n0000000252 00000 n\ntrailer<</Size 5/Root 1 0 R>>\nstartxref\n400\n%%EOF"
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    try:
        pdf_res = await cli.tools.execute_tool("summarize_pdf", filepath=pdf_path)
        print(f"✓ PDF Extraction Result:\n{pdf_res}\n")
        assert "CLAIM" in pdf_res or "Raw Extracted PDF Content" in pdf_res
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

asyncio.run(run_student_tests())

print("All Student Features (Phase 1) tests PASSED successfully!")
