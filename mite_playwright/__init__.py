"""Mite Playwright adapter for browser testing with performance metrics."""

__version__ = "1.0.0"

from .playwright_runner import (
    mite_playwright,
    _PlaywrightWrapper as PlaywrightWrapper,
    _PlaywrightWireWrapper as PlaywrightWireWrapper,
    JsMetricsContext,
)

__all__ = [
    "mite_playwright",
    "PlaywrightWrapper",
    "PlaywrightWireWrapper", 
    "JsMetricsContext",
]

