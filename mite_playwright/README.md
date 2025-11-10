# Mite Playwright Adapter

A streamlined Playwright adapter for the mite performance testing framework, providing browser automation with comprehensive performance metrics.

## Features

- **Familiar API**: Intuitive methods (`get`, `click`, `fill`, `login`)
- **Automatic Performance Metrics**: Core Web Vitals, timing data, resource loading
- **Mite Framework Integration**: Seamless integration with existing mite workflows  
- **Multi-Browser Support**: Chromium, Firefox, and WebKit
- **Zero Configuration**: Works out of the box with sensible defaults

## Installation

```bash
pip install playwright
playwright install
```

## Quick Start

```python
from mite_playwright import mite_playwright

@mite_playwright
async def test_example(ctx):
    """Simple test with automatic metrics collection"""
    await ctx.browser.get("https://example.com")
    await ctx.browser.click("button")
    await ctx.browser.fill("input[name='search']", "test query")
```

## Usage Examples

### Basic Test with Login

```python
from mite_playwright import mite_playwright

@mite_playwright  
async def login_test(ctx):
    """Test login flow with built-in helper"""
    await ctx.browser.get("https://app.example.com")
    await ctx.browser.login("user@example.com", "password123")
    await ctx.browser.wait_for_element(".dashboard")
```

### Direct Browser Usage

```python
from mite_playwright import PlaywrightWrapper

async def standalone_test():
    async with PlaywrightWrapper() as browser:
        await browser.get("https://example.com")
        await browser.click("nav a[href='/about']")
```

##  Performance Metrics

Automatically collected metrics include:

- **Core Web Vitals**: FCP, LCP timing
- **Navigation Timing**: DNS, TCP, DOM interactive, load complete
- **Resource Loading**: JavaScript resources, network requests

## API Reference

### Core Components

| Component | Purpose |
|-----------|---------|
| `mite_playwright` | Decorator for mite test functions |
| `PlaywrightWrapper` | Direct browser automation |
| `PlaywrightWireWrapper` | Network interception support |
| `JsMetricsContext` | Performance metrics collection |

### Browser Methods

| Method | Description | Example |
|--------|-------------|---------|
| `get(url)` | Navigate with metrics | `await browser.get("https://example.com")` |
| `click(selector)` | Click element | `await browser.click("button.submit")` |
| `fill(selector, text)` | Fill input | `await browser.fill("input[name='email']", "user@example.com")` |
| `wait_for_element(selector)` | Wait for element | `await browser.wait_for_element(".results")` |
| `login(username, password)` | Automated login | `await browser.login("user", "pass")` |

##  Examples

See example files for complete demonstrations:

- **`mite_playwright_example.py`**: Comprehensive metrics collection demonstration

### Running Examples

```bash
python mite_playwright_example.py
```


