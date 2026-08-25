"""
BrowserService for JARVIS Mk4
Persistent Playwright headless browser service with async-sync bridging,
navigation timeouts, idle auto-close, DOM text extraction, screenshots, and link harvesting.
"""

import asyncio
import os
import re
import time
import html
import threading
import uuid
from typing import Optional, List, Dict, Any
from pathlib import Path
from jarvis.config_manager import ConfigManager

config = ConfigManager()


class BrowserService:
    """Singleton/persistent service managing a Playwright headless Chromium instance."""

    def __init__(self):
        self.headless = config.get("browser.headless", True)
        self.nav_timeout_sec = config.get("browser.nav_timeout_seconds", 15)
        self.idle_timeout_sec = config.get("browser.idle_timeout_minutes", 5) * 60
        self.max_screenshot_width = config.get("browser.max_screenshot_width", 1280)

        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._last_active_time = time.time()
        self._idle_timer_handle: Optional[asyncio.TimerHandle] = None
        self._current_url = ""

    def _ensure_loop(self):
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._loop = asyncio.new_event_loop()
                self._thread = threading.Thread(target=self._start_loop, args=(self._loop,), daemon=True)
                self._thread.start()

    def _start_loop(self, loop: asyncio.AbstractEventLoop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def _run_async(self, coro, timeout: Optional[float] = None):
        self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def _reset_idle_timer_in_loop(self):
        if self._idle_timer_handle:
            self._idle_timer_handle.cancel()
            self._idle_timer_handle = None
        if self.idle_timeout_sec > 0 and self._browser:
            self._idle_timer_handle = self._loop.call_later(
                self.idle_timeout_sec,
                lambda: asyncio.create_task(self._auto_close_idle())
            )

    async def _auto_close_idle(self):
        elapsed = time.time() - self._last_active_time
        if elapsed >= self.idle_timeout_sec and self._browser:
            print(f"[BROWSER] Idle timeout ({self.idle_timeout_sec}s) reached. Closing Chromium session.")
            await self._async_close()

    async def _ensure_browser(self):
        self._last_active_time = time.time()
        self._reset_idle_timer_in_loop()

        if self._page and self._browser and self._browser.is_connected():
            return self._page

        try:
            from playwright.async_api import async_playwright
            if not self._playwright:
                self._playwright = await async_playwright().start()

            if not self._browser or not self._browser.is_connected():
                self._browser = await self._playwright.chromium.launch(
                    headless=self.headless,
                    args=["--no-sandbox", "--disable-setuid-sandbox"]
                )

            if not self._context:
                self._context = await self._browser.new_context(
                    viewport={"width": self.max_screenshot_width, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )

            if not self._page or self._page.is_closed():
                self._page = await self._context.new_page()
                self._page.set_default_navigation_timeout(self.nav_timeout_sec * 1000)
                self._page.set_default_timeout(self.nav_timeout_sec * 1000)

            return self._page
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Playwright Chromium: {e}")

    # -------------------------------------------------------------
    # Async Core Implementation
    # -------------------------------------------------------------
    async def _async_navigate(self, url: str, wait_for_selector: Optional[str] = None) -> str:
        page = await self._ensure_browser()
        
        target_url = url.strip()
        if not target_url.startswith(("http://", "https://")):
            target_url = "https://" + target_url

        print(f"[BROWSER] Navigating to {target_url} (timeout: {self.nav_timeout_sec}s)...")
        await page.goto(target_url, wait_until="domcontentloaded", timeout=self.nav_timeout_sec * 1000)

        if wait_for_selector:
            try:
                await page.wait_for_selector(wait_for_selector, timeout=self.nav_timeout_sec * 1000)
            except Exception:
                pass

        self._current_url = page.url
        return await self._async_extract_clean_text(page)

    async def _async_extract_clean_text(self, page) -> str:
        # Use DOM innerText for rendered JS text extraction
        try:
            rendered_text = await page.evaluate('''() => {
                const clone = document.cloneNode(true);
                const removeSelectors = ['script', 'style', 'noscript', 'svg', 'iframe'];
                removeSelectors.forEach(sel => clone.querySelectorAll(sel).forEach(el => el.remove()));
                return clone.body ? clone.body.innerText : '';
            }''')
        except Exception:
            rendered_text = ""

        if not rendered_text or not rendered_text.strip():
            content = await page.content()
            clean = re.sub(r'<(script|style|noscript|svg|iframe)[^>]*>[\s\S]*?</\1>', '', content, flags=re.IGNORECASE)
            clean = re.sub(r'<[^>]+>', ' ', clean)
            rendered_text = html.unescape(clean)

        lines = [line.strip() for line in rendered_text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)
        return clean_text[:4000] if len(clean_text) > 4000 else clean_text

    async def _async_click(self, selector_description: str) -> str:
        page = await self._ensure_browser()
        desc = selector_description.strip()

        # Try exact selector first if provided (e.g. #submit, .btn-login, button[name='search'])
        target_found = False
        selectors_to_try = [
            desc,
            f"text={desc}",
            f"button:has-text('{desc}')",
            f"a:has-text('{desc}')",
            f"[aria-label*='{desc}' i]",
            f"[placeholder*='{desc}' i]"
        ]

        for sel in selectors_to_try:
            try:
                elem = page.locator(sel).first
                if await elem.is_visible(timeout=1000):
                    await elem.click(timeout=self.nav_timeout_sec * 1000)
                    target_found = True
                    break
            except Exception:
                continue

        if not target_found:
            raise RuntimeError(f"Could not find clickable element matching '{selector_description}' on page {page.url}")

        await page.wait_for_load_state("domcontentloaded", timeout=self.nav_timeout_sec * 1000)
        self._current_url = page.url
        return await self._async_extract_clean_text(page)

    async def _async_take_screenshot(self) -> str:
        page = await self._ensure_browser()
        screenshots_dir = Path("jarvis/data/screenshots")
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"screenshot_{int(time.time())}_{uuid.uuid4().hex[:6]}.png"
        filepath = screenshots_dir / filename
        
        await page.screenshot(path=str(filepath), full_page=False)
        return str(filepath.resolve())

    async def _async_extract_links(self, url: Optional[str] = None) -> List[Dict[str, str]]:
        page = await self._ensure_browser()
        if url and url.strip():
            await self._async_navigate(url)

        links_data = await page.evaluate('''() => {
            const anchors = Array.from(document.querySelectorAll('a[href]'));
            return anchors.map(a => ({
                text: a.innerText.trim() || a.getAttribute('title') || a.getAttribute('aria-label') || 'Link',
                href: a.href
            })).filter(l => l.href && !l.href.startsWith('javascript:'));
        }''')
        return links_data[:50]

    async def _async_close(self):
        if self._idle_timer_handle:
            self._idle_timer_handle.cancel()
            self._idle_timer_handle = None

        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None

        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        self._page = None
        self._current_url = ""
        print("[BROWSER] Session closed successfully.")

    # -------------------------------------------------------------
    # Public Synchronous Interface
    # -------------------------------------------------------------
    def navigate(self, url: str, wait_for_selector: Optional[str] = None) -> str:
        """Navigate to URL, render JS, and return clean page text."""
        return self._run_async(self._async_navigate(url, wait_for_selector), timeout=self.nav_timeout_sec + 5)

    def click(self, selector_description: str) -> str:
        """Click element by selector or description and return updated page text."""
        return self._run_async(self._async_click(selector_description), timeout=self.nav_timeout_sec + 5)

    def screenshot(self) -> str:
        """Capture screenshot and return absolute file path."""
        return self.take_screenshot()

    def take_screenshot(self) -> str:
        """Capture screenshot and return absolute file path."""
        return self._run_async(self._async_take_screenshot(), timeout=15)

    def extract_links(self, url: Optional[str] = None) -> List[Dict[str, str]]:
        """Harvest link anchors and hrefs from current or target page."""
        return self._run_async(self._async_extract_links(url), timeout=self.nav_timeout_sec + 5)

    def close(self):
        """Explicitly close Playwright browser session."""
        if self._loop and self._loop.is_running():
            return self._run_async(self._async_close(), timeout=10)
