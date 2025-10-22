"""
Simple Playwright adapter for mite performance testing framework

A lightweight browser automation adapter using Playwright.
"""

# Simple imports
try:
    from .simple_runner import SimplePlaywrightRunner
    from .simple_scenario import SimplePlaywrightScenario, SimplePageLoadScenario, SimpleLoginScenario
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    SimplePlaywrightRunner = None
    SimplePlaywrightScenario = None
    SimplePageLoadScenario = None
    SimpleLoginScenario = None
    PLAYWRIGHT_AVAILABLE = False

__version__ = "1.0.0"

__all__ = [
    "SimplePlaywrightRunner", 
    "SimplePlaywrightScenario", 
    "SimplePageLoadScenario", 
    "SimpleLoginScenario"
] if PLAYWRIGHT_AVAILABLE else []