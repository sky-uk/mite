# Mite Playwright Adapter

A high-performance Playwright adapter for the mite load testing framework, optimized for native metrics collection and browser automation.

## Features

- ** Native Playwright Integration**: Full async/await support with modern browser automation
- ** Real Timing Metrics**: Collects actual network timing using correct Playwright APIs
- ** Multi-Browser Support**: Chromium, Firefox, and WebKit
- ** Advanced Configuration**: Comprehensive browser and context configuration options
- ** Network Interception**: Built-in request/response interception capabilities
- ** Automatic Login**: Pre-built login functionality with metrics collection

## Installation

```bash
pip install playwright
pip install mite-playwright
```

##  Quick Start

```python
from _PlaywrightWireWrapper import mite_playwright

@mite_playwright
async def test_website_performance(ctx):
    # Create a new page
    page = await ctx.browser.new_page()
    
    # Navigate with automatic native metrics collection
    await ctx.browser.goto(page, "https://example.com")
        
```

##  Available Native Metrics

The adapter collects **real timing data** using Playwright's native timing APIs with correct property names:

###  Network Timing Metrics
- `dns_lookup_time` - DNS resolution duration (from `domainLookupStart/End`)
- `tcp_time` - TCP connection establishment (from `connectStart/End`)
- `tls_time` - TLS handshake duration (from `secureConnectionStart/connectEnd`)
- `time_to_first_byte` - Network TTFB (from `requestStart/responseStart`)
- `time_to_last_byte` - Complete response time (from `requestStart/responseEnd`)
- `total_time` - Total request duration (from `requestStart/responseEnd`)

###  Request/Response Metrics  
- `request_start_time` - Request initiation timestamp (from `requestStart`)
- `response_start_time` - Response start timestamp (from `responseStart`)
- `response_end_time` - Response completion timestamp (from `responseEnd`)
- `response_size` - Response content size (from headers)
- `status_code` - HTTP response status
- `url` - Request URL

### Execution Metrics
- `execution_time` - Context execution duration

##  Configuration

### Basic Browser Configuration

```
config = {
    "browser_name": "chromium",  # chromium, firefox, webkit
    "browser_headless": True,
    "browser_viewport": {"width": 1280, "height": 720},
    "browser_timeout": 30000,
    "browser_navigation_timeout": 30000,
}

```


##  Performance Benefits

### Fixed Native Timing Collection

This adapter now uses **correct Playwright timing property names**:

| Metric | Playwright Source | Description |
|--------|------------------|-------------|
| **DNS Lookup** | `domainLookupStart/End` | Real DNS resolution timing |
| **TCP Connect** | `connectStart/End` | Actual TCP connection time |
| **TLS Handshake** | `secureConnectionStart/connectEnd` | SSL/TLS negotiation |
| **TTFB** | `requestStart/responseStart` | True time to first byte |
| **Total Time** | `requestStart/responseEnd` | Complete request duration |

