"""
Simple Playwright Runner - Basic browser automation

A simplified runner for browser automation using Playwright.
"""

import asyncio
import time

# Handle missing Playwright dependency gracefully
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class SimplePlaywrightRunner:
    """Simple Playwright runner for basic browser automation"""
    
    def __init__(self, headless=True, browser_type="chromium"):
        """
        Initialize simple runner.
        
        Args:
            headless: Run browser in headless mode
            browser_type: Browser type (chromium, firefox, webkit)
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright not installed. Run: pip install playwright && playwright install")
        
        self.headless = headless
        self.browser_type = browser_type
        self.playwright = None
        self.browser = None
        self.page = None
    
    async def start(self):
        """Start browser"""
        self.playwright = await async_playwright().start()
        
        if self.browser_type == "chromium":
            self.browser = await self.playwright.chromium.launch(headless=self.headless)
        elif self.browser_type == "firefox":
            self.browser = await self.playwright.firefox.launch(headless=self.headless)
        elif self.browser_type == "webkit":
            self.browser = await self.playwright.webkit.launch(headless=self.headless)
        else:
            raise ValueError(f"Unsupported browser: {self.browser_type}")
        
        context = await self.browser.new_context()
        self.page = await context.new_page()
    
    async def stop(self):
        """Stop browser"""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def goto(self, url):
        """Navigate to URL"""
        start_time = time.time()
        await self.page.goto(url)
        return (time.time() - start_time) * 1000  # Return time in ms
    
    async def click(self, selector):
        """Click element"""
        start_time = time.time()
        await self.page.click(selector)
        return (time.time() - start_time) * 1000
    
    async def fill(self, selector, text):
        """Fill input field"""
        start_time = time.time()
        await self.page.fill(selector, text)
        return (time.time() - start_time) * 1000
    
    async def wait_for(self, selector, timeout=30000):
        """Wait for element"""
        start_time = time.time()
        await self.page.wait_for_selector(selector, timeout=timeout)
        return (time.time() - start_time) * 1000
    
    async def get_text(self, selector):
        """Get text from element"""
        element = await self.page.wait_for_selector(selector)
        return await element.text_content()
    
    async def screenshot(self, path):
        """Take screenshot"""
        await self.page.screenshot(path=path)