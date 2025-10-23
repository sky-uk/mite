"""
Mite Playwright Adapter

A Playwright adapter for the mite performance testing framework, 
designed to match the structure and functionality of mite_selenium.

This adapter provides browser automation capabilities using Playwright
for performance testing scenarios.
"""

__version__ = "1.0.0"

from .runner import PlaywrightMiteRunner
from .stats import PlaywrightStats, PlaywrightStatsCollector
from .utils import (
    create_browser_config,
    wait_for_page_load,
    safe_click,
    safe_fill,
    element_exists
)

__all__ = [
    'PlaywrightMiteRunner',
    'PlaywrightStats',
    'PlaywrightStatsCollector', 
    'create_browser_config',
    'wait_for_page_load',
    'safe_click',
    'safe_fill',
    'element_exists'
]