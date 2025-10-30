"""
Playwright Utils Module

Utility functions and helpers for Playwright automation.
Similar to mite_selenium utils but optimized for Playwright API.
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, Union, List
from playwright.async_api import Page, ElementHandle, BrowserContext

logger = logging.getLogger(__name__)


def create_browser_config(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create and validate browser configuration.
    Similar to Selenium config but for Playwright browsers.
    
    Args:
        config: User-provided configuration dictionary
        
    Returns:
        Validated configuration with defaults
    """
    defaults = {
        'browser': 'chromium',
        'headless': True,
        'timeout': 30000,
        'navigation_timeout': 30000,
        'launch_options': {
            'headless': True,
            'args': [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security'
            ]
        },
        'context_options': {
            'viewport': {'width': 1280, 'height': 720},
            'ignore_https_errors': True,
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
    }
    
    if config:
        # Merge user config with defaults
        merged_config = defaults.copy()
        merged_config.update(config)
        
        # Update nested dictionaries
        if 'launch_options' in config:
            merged_config['launch_options'].update(config['launch_options'])
        if 'context_options' in config:
            merged_config['context_options'].update(config['context_options'])
            
        # Sync headless setting
        merged_config['launch_options']['headless'] = merged_config.get('headless', True)
        
        return merged_config
    
    return defaults


async def wait_for_page_load(page: Page, timeout: int = 30000, wait_until: str = 'networkidle') -> float:
    """
    Wait for page to fully load with timing measurement.
    
    Args:
        page: Playwright page object
        timeout: Timeout in milliseconds
        wait_until: Load state to wait for
        
    Returns:
        Wait time in milliseconds
    """
    start_time = time.time()
    
    try:
        await page.wait_for_load_state(wait_until, timeout=timeout)
        return (time.time() - start_time) * 1000
    except Exception as e:
        logger.warning(f"Page load wait failed: {e}")
        return (time.time() - start_time) * 1000


async def safe_click(page: Page, selector: str, timeout: int = 30000, **options) -> bool:
    """
    Safely click an element with error handling.
    
    Args:
        page: Playwright page object
        selector: CSS selector for element
        timeout: Timeout in milliseconds
        **options: Additional click options
        
    Returns:
        True if successful, False otherwise
    """
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        await page.click(selector, **options)
        return True
    except Exception as e:
        logger.error(f"Safe click failed for {selector}: {e}")
        return False


async def safe_fill(page: Page, selector: str, value: str, timeout: int = 30000, **options) -> bool:
    """
    Safely fill an input field with error handling.
    
    Args:
        page: Playwright page object
        selector: CSS selector for input element
        value: Value to fill
        timeout: Timeout in milliseconds
        **options: Additional fill options
        
    Returns:
        True if successful, False otherwise
    """
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        await page.fill(selector, value, **options)
        return True
    except Exception as e:
        logger.error(f"Safe fill failed for {selector}: {e}")
        return False


async def element_exists(page: Page, selector: str, timeout: int = 5000) -> bool:
    """
    Check if element exists on page.
    
    Args:
        page: Playwright page object
        selector: CSS selector for element
        timeout: Timeout in milliseconds
        
    Returns:
        True if element exists, False otherwise
    """
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        return True
    except:
        return False


async def get_element_text(page: Page, selector: str, timeout: int = 30000) -> Optional[str]:
    """
    Get text content of an element.
    
    Args:
        page: Playwright page object
        selector: CSS selector for element
        timeout: Timeout in milliseconds
        
    Returns:
        Element text or None if not found
    """
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        return await page.text_content(selector)
    except Exception as e:
        logger.error(f"Failed to get text from {selector}: {e}")
        return None


async def get_element_attribute(page: Page, selector: str, attribute: str, timeout: int = 30000) -> Optional[str]:
    """
    Get attribute value of an element.
    
    Args:
        page: Playwright page object
        selector: CSS selector for element
        attribute: Attribute name
        timeout: Timeout in milliseconds
        
    Returns:
        Attribute value or None if not found
    """
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        return await page.get_attribute(selector, attribute)
    except Exception as e:
        logger.error(f"Failed to get attribute {attribute} from {selector}: {e}")
        return None


async def scroll_to_element(page: Page, selector: str, timeout: int = 30000) -> bool:
    """
    Scroll to element on page.
    
    Args:
        page: Playwright page object
        selector: CSS selector for element
        timeout: Timeout in milliseconds
        
    Returns:
        True if successful, False otherwise
    """
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        await page.locator(selector).scroll_into_view_if_needed()
        return True
    except Exception as e:
        logger.error(f"Failed to scroll to {selector}: {e}")
        return False


async def select_option(page: Page, selector: str, value: Union[str, List[str]], timeout: int = 30000) -> bool:
    """
    Select option from dropdown.
    
    Args:
        page: Playwright page object
        selector: CSS selector for select element
        value: Option value(s) to select
        timeout: Timeout in milliseconds
        
    Returns:
        True if successful, False otherwise
    """
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        await page.select_option(selector, value)
        return True
    except Exception as e:
        logger.error(f"Failed to select option {value} from {selector}: {e}")
        return False


async def upload_file(page: Page, selector: str, file_path: str, timeout: int = 30000) -> bool:
    """
    Upload file to input field.
    
    Args:
        page: Playwright page object
        selector: CSS selector for file input
        file_path: Path to file to upload
        timeout: Timeout in milliseconds
        
    Returns:
        True if successful, False otherwise
    """
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        await page.set_input_files(selector, file_path)
        return True
    except Exception as e:
        logger.error(f"Failed to upload file to {selector}: {e}")
        return False


async def wait_for_navigation(page: Page, timeout: int = 30000) -> float:
    """
    Wait for navigation to complete and measure timing.
    
    Args:
        page: Playwright page object
        timeout: Timeout in milliseconds
        
    Returns:
        Navigation time in milliseconds
    """
    start_time = time.time()
    
    try:
        await page.wait_for_load_state('networkidle', timeout=timeout)
        return (time.time() - start_time) * 1000
    except Exception as e:
        logger.warning(f"Navigation wait failed: {e}")
        return (time.time() - start_time) * 1000


class PlaywrightPageHelper:
    """
    Helper class for common page operations.
    Similar to Selenium page helper but for Playwright.
    """
    
    def __init__(self, page: Page):
        """
        Initialize page helper.
        
        Args:
            page: Playwright page object
        """
        self.page = page
        
    async def login(self, username_selector: str, password_selector: str,
                   submit_selector: str, username: str, password: str) -> Dict[str, Any]:
        """
        Perform login operation with timing.
        
        Args:
            username_selector: Username field selector
            password_selector: Password field selector
            submit_selector: Submit button selector
            username: Username value
            password: Password value
            
        Returns:
            Dictionary with timing metrics
        """
        metrics = {}
        
        # Fill username
        start_time = time.time()
        success = await safe_fill(self.page, username_selector, username)
        metrics['username_fill_time'] = (time.time() - start_time) * 1000
        metrics['username_fill_success'] = success
        
        # Fill password
        start_time = time.time()
        success = await safe_fill(self.page, password_selector, password)
        metrics['password_fill_time'] = (time.time() - start_time) * 1000
        metrics['password_fill_success'] = success
        
        # Click submit
        start_time = time.time()
        success = await safe_click(self.page, submit_selector)
        metrics['submit_click_time'] = (time.time() - start_time) * 1000
        metrics['submit_click_success'] = success
        
        # Wait for navigation
        nav_time = await wait_for_navigation(self.page)
        metrics['post_login_navigation_time'] = nav_time
        
        return metrics
        
    async def fill_form(self, form_data: Dict[str, str], submit_selector: str = None) -> Dict[str, Any]:
        """
        Fill multiple form fields with timing.
        
        Args:
            form_data: Dictionary of selector -> value pairs
            submit_selector: Optional submit button selector
            
        Returns:
            Dictionary with timing metrics
        """
        metrics = {}
        total_start = time.time()
        
        for selector, value in form_data.items():
            start_time = time.time()
            success = await safe_fill(self.page, selector, value)
            field_time = (time.time() - start_time) * 1000
            
            metrics[f'field_{selector}_time'] = field_time
            metrics[f'field_{selector}_success'] = success
            
        if submit_selector:
            start_time = time.time()
            success = await safe_click(self.page, submit_selector)
            metrics['submit_time'] = (time.time() - start_time) * 1000
            metrics['submit_success'] = success
            
        metrics['total_form_time'] = (time.time() - total_start) * 1000
        return metrics
        
    async def get_page_info(self) -> Dict[str, Any]:
        """
        Get basic page information.
        
        Returns:
            Dictionary with page information
        """
        return {
            'title': await self.page.title(),
            'url': self.page.url,
            'viewport': self.page.viewport_size
        }


def format_timing_stats(stats: Dict[str, Any]) -> str:
    """
    Format timing statistics for display.
    
    Args:
        stats: Statistics dictionary
        
    Returns:
        Formatted string
    """
    lines = []
    lines.append("Playwright Performance Stats:")
    lines.append("=" * 30)
    
    if 'navigation' in stats:
        nav = stats['navigation']
        lines.append(f"Navigation: {nav.get('count', 0)} requests")
        lines.append(f"  Avg: {nav.get('avg_time', 0):.2f}ms")
        lines.append(f"  Min/Max: {nav.get('min_time', 0):.2f}/{nav.get('max_time', 0):.2f}ms")
        
    if 'actions' in stats:
        actions = stats['actions']
        for action_type, action_stats in actions.items():
            count = action_stats.get('count', 0)
            avg_time = action_stats.get('avg_time', 0)
            lines.append(f"{action_type.title()}: {count} actions (avg: {avg_time:.2f}ms)")
            
    if 'errors' in stats:
        error_count = stats['errors'].get('count', 0)
        lines.append(f"Errors: {error_count}")
        
    return "\n".join(lines)