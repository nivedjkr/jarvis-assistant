"""
Global Awareness Module for JARVIS
Monitors news topics, deduplicates headlines, scores significance via LLM,
and surfaces notable updates proactively.
"""

import os
import json
import time
import asyncio
import threading
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from rich.console import Console

console = Console()


class GlobalAwarenessManager:
    """Manages background news monitoring, deduplication, significance scoring, and surfacing"""

    def __init__(
        self,
        config: dict,
        api_client: Optional[Any] = None,
        proactive_monitor: Optional[Any] = None,
        data_dir: str = "jarvis/data"
    ):
        self.config = config
        self.awareness_config = config.get("awareness", {})
        self.enabled = self.awareness_config.get("enabled", True)
        self.topics = list(self.awareness_config.get("topics", ["AI", "cybersecurity", "space technology"]))
        self.check_interval_hours = float(self.awareness_config.get("check_interval_hours", 3))
        self.significance_threshold = int(self.awareness_config.get("significance_threshold", 7))
        
        self.api_client = api_client
        self.proactive_monitor = proactive_monitor
        
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.seen_file = self.data_dir / "awareness_seen.json"
        self.surfaced_file = self.data_dir / "surfaced_news.json"
        
        self.seen_urls = self._load_seen()
        self.surfaced_news = self._load_surfaced()
        
        self.running = False
        self.thread = None

    def _load_seen(self) -> set:
        """Load seen article URLs from JSON file"""
        if self.seen_file.exists():
            try:
                with open(self.seen_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data)
            except Exception as e:
                console.print(f"[yellow]Error loading awareness seen data: {e}[/yellow]")
        return set()

    def _save_seen(self):
        """Save seen article URLs to JSON file"""
        try:
            with open(self.seen_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.seen_urls), f, indent=2)
        except Exception as e:
            console.print(f"[red]Error saving awareness seen data: {e}[/red]")

    def _load_surfaced(self) -> List[Dict[str, Any]]:
        """Load surfaced news items from JSON file"""
        if self.surfaced_file.exists():
            try:
                with open(self.surfaced_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                console.print(f"[yellow]Error loading surfaced news data: {e}[/yellow]")
        return []

    def _save_surfaced(self):
        """Save surfaced news items to JSON file"""
        try:
            with open(self.surfaced_file, 'w', encoding='utf-8') as f:
                json.dump(self.surfaced_news, f, indent=2)
        except Exception as e:
            console.print(f"[red]Error saving surfaced news data: {e}[/red]")

    def fetch_topic_news(self, topic: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        Fetch news articles for a given topic using Google News RSS feed
        """
        articles = []
        try:
            encoded_topic = urllib.parse.quote(topic)
            rss_url = f"https://news.google.com/rss/search?q={encoded_topic}&hl=en-US&gl=US&ceid=US:en"
            
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            req = urllib.request.Request(rss_url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=10) as response:
                xml_data = response.read()
                
            root = ET.fromstring(xml_data)
            channel = root.find("channel")
            if channel is None:
                return []

            for item in channel.findall("item")[:max_results]:
                title = item.findtext("title", default="").strip()
                link = item.findtext("link", default="").strip()
                pub_date = item.findtext("pubDate", default="").strip()
                description = item.findtext("description", default="").strip()
                
                # Basic HTML cleaning for description
                import re
                clean_desc = re.sub(r'<[^>]+>', '', description).strip()

                if title and link:
                    articles.append({
                        "topic": topic,
                        "title": title,
                        "link": link,
                        "pub_date": pub_date,
                        "description": clean_desc
                    })

        except Exception as e:
            console.print(f"[dim yellow]Warning: Failed to fetch RSS news for topic '{topic}': {e}[/dim yellow]")
        
        return articles

    async def score_article_significance(self, topic: str, article: Dict[str, str]) -> Tuple[int, str]:
        """
        Use LLM to evaluate article significance (1-10) and generate a spoken one-liner.
        """
        if not self.api_client or not hasattr(self.api_client, 'client'):
            # Fallback when LLM client is unavailable
            return 7, article["title"]

        prompt = (
            f"Topic: {topic}\n"
            f"Headline: {article['title']}\n"
            f"Snippet: {article['description']}\n\n"
            "Task: Evaluate if this news item is genuinely notable and high-impact "
            "(e.g. major tech breakthrough, critical vulnerability, major industry event) "
            "versus routine opinion/blog post.\n"
            "Respond ONLY with a JSON object: {\"score\": <1-10 integer>, \"one_liner\": \"<Short 1-sentence spoken summary>\"}"
        )

        try:
            response = await self.api_client.client.chat.completions.create(
                model=self.api_client.config["api"]["model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=150
            )

            if response.choices and response.choices[0].message.content:
                raw = response.choices[0].message.content.strip()
                import re
                match = re.search(r'\{.*\}', raw, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    score = int(data.get("score", 5))
                    one_liner = str(data.get("one_liner", article["title"])).strip()
                    return score, one_liner
        except Exception as e:
            console.print(f"[dim yellow]LLM scoring failed: {e}[/dim yellow]")

        return 7, article["title"]

    async def check_news(self) -> List[Dict[str, Any]]:
        """
        Perform a full check across all watched topics:
        Fetch -> Deduplicate -> Score Significance -> Surface Notable Items
        """
        if not self.enabled:
            return []

        console.print("[dim cyan]🌐 Global Awareness: checking news for watched topics...[/dim cyan]")
        newly_surfaced = []

        for topic in self.topics:
            articles = self.fetch_topic_news(topic, max_results=5)
            
            for article in articles:
                link = article["link"]
                # Deduplicate by URL or title
                if link in self.seen_urls or article["title"] in self.seen_urls:
                    continue

                # Mark as seen
                self.seen_urls.add(link)
                self.seen_urls.add(article["title"])

                # Score significance
                score, one_liner = await self.score_article_significance(topic, article)
                
                if score >= self.significance_threshold:
                    item = {
                        "id": len(self.surfaced_news) + 1,
                        "topic": topic,
                        "headline": article["title"],
                        "one_liner": one_liner,
                        "link": link,
                        "score": score,
                        "pub_date": article["pub_date"],
                        "timestamp": datetime.now().isoformat()
                    }
                    self.surfaced_news.insert(0, item)  # Newest first
                    newly_surfaced.append(item)

                    # Queue proactive voice announcement if proactive monitor available
                    if self.proactive_monitor and hasattr(self.proactive_monitor, '_queue_announcement'):
                        user_title = getattr(self.api_client, 'user_title', 'sir') if self.api_client else 'sir'
                        announcement = f"{user_title.capitalize()}, notable update in {topic}: {one_liner}. Type /news to review."
                        self.proactive_monitor._queue_announcement(announcement)

        self._save_seen()
        if newly_surfaced:
            self._save_surfaced()
            console.print(f"[cyan]🌐 Surfaced {len(newly_surfaced)} notable news update(s).[/cyan]")
        else:
            console.print("[dim]🌐 Global Awareness check completed: no new notable updates.[/dim]")

        return newly_surfaced

    def _monitor_loop(self):
        """Background monitoring thread loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Initial delay before first background check
        time.sleep(10)

        while self.running:
            try:
                if self.enabled:
                    loop.run_until_complete(self.check_news())
            except Exception as e:
                console.print(f"[red]Global Awareness monitor error: {e}[/red]")

            # Sleep interval in seconds
            sleep_secs = int(self.check_interval_hours * 3600)
            
            # Check running state periodically during long sleep
            slept = 0
            while slept < sleep_secs and self.running:
                time.sleep(5)
                slept += 5

    def start(self):
        """Start the background monitor thread"""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        console.print("[dim]Global Awareness monitor started[/dim]")

    def stop(self):
        """Stop the background monitor thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
        console.print("[dim]Global Awareness monitor stopped[/dim]")

    def set_enabled(self, enabled: bool):
        """Enable or disable monitoring"""
        self.enabled = enabled
        self.awareness_config["enabled"] = enabled

    def get_topics(self) -> List[str]:
        """Get list of watched topics"""
        return self.topics

    def add_topic(self, topic: str) -> bool:
        """Add a watched topic"""
        t_clean = topic.strip()
        if t_clean and t_clean not in self.topics:
            self.topics.append(t_clean)
            self.awareness_config["topics"] = self.topics
            return True
        return False

    def remove_topic(self, topic: str) -> bool:
        """Remove a watched topic"""
        t_clean = topic.strip()
        for t in list(self.topics):
            if t.lower() == t_clean.lower():
                self.topics.remove(t)
                self.awareness_config["topics"] = self.topics
                return True
        return False

    def get_surfaced_news(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Get recent surfaced news items"""
        return self.surfaced_news[:limit]
