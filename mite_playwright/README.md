# Mite Playwright - Automatic Performance Metrics Collection

A transparent wrapper for Playwright that automatically collects comprehensive performance metrics during web automation testing.

## Overview

`mite_playwright` provides seamless integration with Playwright, automatically capturing detailed performance metrics including DNS timing, TCP/TLS handshake times, paint events, and browser performance data without requiring any changes to your existing Playwright code.

## Features

- **Zero Code Changes** - Works with existing Playwright scripts
- **Comprehensive Metrics** - Network timing, paint events, page load metrics
- **Transparent Proxy** - Intercepts all Playwright operations automatically
- **Navigation Focused** - Captures metrics for page navigation operations
- **Performance Optimized** - Minimal overhead on test execution
- **Error Handling** - Automatic error tracking and reporting

## Quick Start

### Installation

```bash
pip install playwright
```

### Basic Usage

```python
from mite_playwright import mite_playwright

@mite_playwright
async def simple_test(ctx, playwright):
    """Simple navigation test with automatic metrics"""
    browser = await playwright.chromium.launch()
    page = await browser.new_page()
    
    # Metrics automatically collected on navigation
    await page.goto("https://example.com")
    
    await browser.close()
```

### Mock Context for Testing

```python
class MockContext:
    def __init__(self):
        self.config = {}

    def send(self, metric_name, **kwargs):
        print(f"METRIC: {metric_name}")
        for key, value in kwargs.items():
            if isinstance(value, float):
                print(f"   {key}: {value:.4f}")
            else:
                print(f"   {key}: {value}")

# Run your test
ctx = MockContext()
asyncio.run(simple_test(ctx))
```

## Collected Metrics

### Network Timing Metrics

| Metric | Description | Unit |
|--------|-------------|------|
| `dns_lookup_time` | DNS resolution time | seconds |
| `tcp_time` | TCP connection establishment | seconds |
| `tls_time` | TLS handshake time (HTTPS only) | seconds |
| `time_to_first_byte` | Time until first response byte | seconds |
| `time_to_last_byte` | Time until response complete | seconds |
| `total_time` | Complete request duration | seconds |

### Response Metrics

| Metric | Description |
|--------|-------------|
| `url` | Requested URL |
| `status` | HTTP status code |
| `response_size` | Content-Length in bytes |
| `request_start_time` | Request start timestamp |
| `response_start_time` | Response start timestamp |
| `response_end_time` | Response end timestamp |

### Paint & Performance Metrics

| Metric | Description | Unit |
|--------|-------------|------|
| `first_paint` | First paint event | seconds |
| `first_contentful_paint` | First contentful paint | seconds |
| `js_onload_time` | JavaScript onload complete | seconds |
| `render_time` | Page render time | seconds |
| `time_to_interactive` | Time to interactive | seconds |
| `page_weight` | Total page size including resources | bytes |

### Error Tracking

The wrapper automatically captures and reports errors:

```python
# Automatic error metrics for:
- Navigation failures
- Timeout errors  
- Element not found errors
- Any Playwright exceptions

# Sent as: playwright_error with method name and error details
```

## File Structure

```
mite_playwright/
├── __init__.py           # Main wrapper implementation
├── mite_playwright_example.py  # Usage examples
├── stats.py              # Statistics utilities
└── README.md             # This documentation
```

## Troubleshooting

### Common Issues

**No metrics collected:**
- Ensure you're using navigation methods (`goto`, `reload`, etc.)
- Check that responses have valid timing data
- Verify your context implements the `send()` method

**Import errors:**
- Install Playwright: `pip install playwright`
- Install browsers: `playwright install`

