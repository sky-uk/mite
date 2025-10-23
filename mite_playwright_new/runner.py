"""
Playwright Mite Runner

Main runner class for Playwright browser automation in the mite framework.
Follows the same pattern as mite_selenium runner but uses Playwright instead of Selenium.
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, List, Union
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from .stats import PlaywrightStatsCollector
from .utils import create_browser_config, wait_for_page_load

logger = logging.getLogger(__name__)


class PlaywrightMiteRunner:
    """
    Main runner class for Playwright automation in mite framework.
    
    Provides similar interface to Selenium runner but uses Playwright for
    better performance and modern browser automation capabilities.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize Playwright runner.
        
        Args:
            config: Configuration dictionary for browser and automation settings
        """
        self.config = create_browser_config(config or {})
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.pages: List[Page] = []
        self.stats_collector = PlaywrightStatsCollector()
        self._loop = None
        self._started = False
        
    async def start(self):
        """Start the Playwright browser and initialize context"""
        if self._started:
            logger.warning("Runner already started")
            return
            
        try:
            start_time = time.time()
            
            # Start Playwright
            self.playwright = await async_playwright().start()
            
            # Launch browser
            browser_type = getattr(self.playwright, self.config['browser'])
            self.browser = await browser_type.launch(**self.config['launch_options'])
            
            # Create context
            self.context = await self.browser.new_context(**self.config['context_options'])
            
            # Set default timeouts
            self.context.set_default_timeout(self.config.get('timeout', 30000))
            self.context.set_default_navigation_timeout(self.config.get('navigation_timeout', 30000))
            
            startup_time = (time.time() - start_time) * 1000
            self.stats_collector.add_stat('browser_startup_time', startup_time)
            
            self._started = True
            logger.info(f"Playwright browser started in {startup_time:.2f}ms")
            
        except Exception as e:
            logger.error(f"Failed to start Playwright browser: {e}")
            await self.stop()
            raise
            
    async def stop(self):
        """Stop the browser and cleanup resources"""
        if not self._started:
            return
            
        try:
            # Remove event listeners from pages first
            for page in self.pages[:]:
                try:
                    # Remove event listeners to prevent orphaned tasks
                    page.remove_listener("pageerror", self._on_page_error)
                    # Wait a moment for any pending operations
                    await asyncio.sleep(0.05)
                    await page.close()
                except Exception as e:
                    logger.warning(f"Error closing page: {e}")
            self.pages.clear()
            
            # Close context
            if self.context:
                try:
                    await self.context.close()
                except Exception as e:
                    logger.warning(f"Error closing context: {e}")
                self.context = None
                
            # Close browser
            if self.browser:
                try:
                    await self.browser.close()
                except Exception as e:
                    logger.warning(f"Error closing browser: {e}")
                self.browser = None
                
            # Stop Playwright
            if self.playwright:
                try:
                    await self.playwright.stop()
                except Exception as e:
                    logger.warning(f"Error stopping playwright: {e}")
                self.playwright = None
                
            self._started = False
            logger.info("Playwright browser stopped")
            
        except Exception as e:
            logger.error(f"Error stopping browser: {e}")
            
    async def new_page(self) -> Page:
        """
        Create a new page in the current context.
        
        Returns:
            New Playwright page object
        """
        if not self._started or not self.context:
            raise RuntimeError("Runner not started. Call start() first.")
            
        page = await self.context.new_page()
        self.pages.append(page)
        
        # Only add basic instrumentation, skip response handler to avoid "Target closed" errors
        page.on("pageerror", self._on_page_error)
        
        return page
        
    async def goto(self, page: Page, url: str, **options) -> Dict[str, Any]:
        """
        Navigate to URL and collect timing metrics.
        
        Args:
            page: Playwright page object
            url: URL to navigate to
            **options: Additional navigation options
            
        Returns:
            Dictionary with navigation metrics
        """
        start_time = time.time()
        
        try:
            response = await page.goto(url, **options)
            await wait_for_page_load(page)
            
            load_time = (time.time() - start_time) * 1000
            
            metrics = {
                'url': url,
                'load_time': load_time,
                'status_code': response.status if response else None,
                'title': await page.title(),
                'final_url': page.url
            }
            
            self.stats_collector.add_navigation_stat(metrics)
            return metrics
            
        except Exception as e:
            error_time = (time.time() - start_time) * 1000
            logger.error(f"Navigation to {url} failed after {error_time:.2f}ms: {e}")
            
            self.stats_collector.add_error('navigation_error', str(e))
            raise
            
    async def click(self, page: Page, selector: str, **options) -> float:
        """
        Click an element and measure timing.
        
        Args:
            page: Playwright page object
            selector: CSS selector for element
            **options: Additional click options
            
        Returns:
            Click time in milliseconds
        """
        start_time = time.time()
        
        try:
            await page.click(selector, **options)
            click_time = (time.time() - start_time) * 1000
            
            self.stats_collector.add_action_stat('click', click_time, selector)
            return click_time
            
        except Exception as e:
            error_time = (time.time() - start_time) * 1000
            logger.error(f"Click on {selector} failed after {error_time:.2f}ms: {e}")
            
            self.stats_collector.add_error('click_error', str(e))
            raise
            
    async def fill(self, page: Page, selector: str, value: str, **options) -> float:
        """
        Fill an input field and measure timing.
        
        Args:
            page: Playwright page object
            selector: CSS selector for input element
            value: Value to fill
            **options: Additional fill options
            
        Returns:
            Fill time in milliseconds
        """
        start_time = time.time()
        
        try:
            await page.fill(selector, value, **options)
            fill_time = (time.time() - start_time) * 1000
            
            self.stats_collector.add_action_stat('fill', fill_time, selector)
            return fill_time
            
        except Exception as e:
            error_time = (time.time() - start_time) * 1000
            logger.error(f"Fill on {selector} failed after {error_time:.2f}ms: {e}")
            
            self.stats_collector.add_error('fill_error', str(e))
            raise
            
    async def wait_for_selector(self, page: Page, selector: str, **options) -> float:
        """
        Wait for element to appear and measure timing.
        
        Args:
            page: Playwright page object
            selector: CSS selector to wait for
            **options: Additional wait options
            
        Returns:
            Wait time in milliseconds
        """
        start_time = time.time()
        
        try:
            await page.wait_for_selector(selector, **options)
            wait_time = (time.time() - start_time) * 1000
            
            self.stats_collector.add_action_stat('wait', wait_time, selector)
            return wait_time
            
        except Exception as e:
            error_time = (time.time() - start_time) * 1000
            logger.error(f"Wait for {selector} failed after {error_time:.2f}ms: {e}")
            
            self.stats_collector.add_error('wait_error', str(e))
            raise
            
    async def screenshot(self, page: Page, path: str = None, **options) -> bytes:
        """Take screenshot of page"""
        return await page.screenshot(path=path, **options)
        
    def get_stats(self) -> Dict[str, Any]:
        """Get collected performance statistics"""
        return self.stats_collector.get_all_stats()
        
    def reset_stats(self):
        """Reset all collected statistics"""
        self.stats_collector.reset()
        
    async def _on_page_error(self, error):
        """Handle page error events"""
        try:
            if self._started and self.stats_collector:
                self.stats_collector.add_error('page_error', str(error))
                logger.error(f"Page error: {error}")
        except Exception:
            # Ignore errors during shutdown
            pass
        
    @asynccontextmanager
    async def managed_session(self):
        """
        Context manager for automatic browser lifecycle management.
        Similar to Selenium's managed session pattern.
        """
        try:
            await self.start()
            yield self
        finally:
            await self.stop()
            
    def __repr__(self):
        status = "started" if self._started else "stopped"
        return f"PlaywrightMiteRunner(browser={self.config['browser']}, status={status})"