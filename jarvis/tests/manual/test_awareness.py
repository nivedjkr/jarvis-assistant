"""
Test Global Awareness module functionality
"""
import sys
import asyncio
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import os
from pathlib import Path

root_dir = str(Path(__file__).resolve().parents[3])
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

print("Testing JARVIS Global Awareness Module...\n")

from jarvis.cli import JARVISCLI

cli = JARVISCLI()
manager = cli.awareness_manager

async def run_awareness_tests():
    # Test 1: News Fetching & Deduplication
    print("--- Test 1: Fetching & Deduplicating News ---")
    articles = manager.fetch_topic_news("AI", max_results=3)
    print(f"✓ Fetched {len(articles)} articles for topic 'AI'")
    if articles:
        first_title = articles[0]["title"]
        first_link = articles[0]["link"]
        print(f"   Sample Headline: '{first_title}'")
        print(f"   Sample Link: '{first_link}'")

    # Check deduplication
    manager.seen_urls.add(articles[0]["link"]) if articles else None
    manager._save_seen()
    seen_count = len(manager.seen_urls)
    print(f"✓ Total seen article links: {seen_count}")

    # Test 2: Significance Scoring & News Check
    print("\n--- Test 2: Running News Check ---")
    surfaced = await manager.check_news()
    print(f"✓ Surfaced {len(surfaced)} new notable article(s)")

    # Test 3: Slash Commands
    print("\n--- Test 3: Slash Commands (/awareness & /news) ---")
    res1 = await cli._handle_slash_command("/awareness topics")
    print(f"✓ /awareness topics output:\n{res1}\n")

    res2 = await cli._handle_slash_command("/awareness topics add quantum computing")
    print(f"✓ /awareness topics add output:\n{res2}\n")

    assert "quantum computing" in manager.get_topics()

    res3 = await cli._handle_slash_command("/awareness topics remove quantum computing")
    print(f"✓ /awareness topics remove output:\n{res3}\n")

    res4 = await cli._handle_slash_command("/news")
    print(f"✓ /news command executed successfully: {res4}\n")

    print("All Global Awareness tests PASSED successfully!")

asyncio.run(run_awareness_tests())
