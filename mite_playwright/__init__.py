"""Mite Playwright adapter for browser testing with performance metrics."""

__version__ = "1.0.0"

from .playwright_runner import JsMetricsContext
from .playwright_runner import _PlaywrightWireWrapper as PlaywrightWireWrapper
from .playwright_runner import _PlaywrightWrapper as PlaywrightWrapper
from .playwright_runner import mite_playwright

__all__ = [
    "mite_playwright",
    "PlaywrightWrapper",
    "PlaywrightWireWrapper",
    "JsMetricsContext",
]
