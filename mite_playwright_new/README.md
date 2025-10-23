# Mite Playwright Adapter

A comprehensive Playwright adapter for the mite performance testing framework, designed to match the structure and functionality of the existing mite_selenium adapter.

## Overview

This adapter provides modern browser automation capabilities using Playwright, offering:

- **High Performance**: Faster and more reliable than Selenium
- **Multi-Browser Support**: Chromium, Firefox, and WebKit
- **Comprehensive Metrics**: Detailed performance statistics collection
- **Mite Integration**: Seamless integration with mite testing framework
- **Modern API**: Async/await support with clean, modern syntax

## Installation

```bash
# Install Playwright
pip install playwright

# Install browser binaries
playwright install

# The adapter uses the same mite framework dependencies
```

## Quick Start

```python
import asyncio
from mite_playwright import PlaywrightMiteRunner

async def simple_test():
    # Configure browser
    config = {
        'browser': 'chromium',
        'headless': True
    }
    
    # Create runner
    runner = PlaywrightMiteRunner(config)
    
    try:
        # Start browser
        await runner.start()
        
        # Create page and navigate
        page = await runner.new_page()
        metrics = await runner.goto(page, 'https://example.com')
        
        # Get performance stats
        stats = runner.get_stats()
        print(f"Load time: {metrics['load_time']:.2f}ms")
        
    finally:
        await runner.stop()

# Run the test
asyncio.run(simple_test())
```

## Architecture

The adapter follows the same modular structure as mite_selenium:

```
mite_playwright/
├── __init__.py          # Package initialization and exports
├── runner.py            # Main PlaywrightMiteRunner class
├── stats.py             # Performance statistics collection
├── utils.py             # Helper functions and utilities
├── examples.py          # Usage examples and patterns
└── README.md           # This documentation
```

### Core Components

#### 1. PlaywrightMiteRunner (`runner.py`)
Main runner class providing:
- Browser lifecycle management (start/stop)
- Page creation and navigation
- Action execution with timing (click, fill, wait)
- Screenshot capture
- Performance metrics collection
- Error handling and logging

#### 2. PlaywrightStats (`stats.py`)
Statistics collection system:
- Navigation timing metrics
- Action performance tracking
- Network request monitoring
- Error tracking and reporting
- Rolling averages and percentiles
- CSV export capabilities

#### 3. Utilities (`utils.py`)
Helper functions and classes:
- Browser configuration management
- Safe element interaction functions
- Page helper for common operations
- Timing measurement decorators
- Error handling utilities

## Configuration

### Browser Configuration

```python
config = {
    'browser': 'chromium',              # 'chromium', 'firefox', 'webkit'
    'headless': True,                   # Run in headless mode
    'timeout': 30000,                   # Default timeout (ms)
    'navigation_timeout': 30000,        # Navigation timeout (ms)
    'launch_options': {
        'headless': True,
        'args': [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu'
        ]
    },
    'context_options': {
        'viewport': {'width': 1280, 'height': 720},
        'ignore_https_errors': True,
        'user_agent': 'Custom User Agent'
    }
}
```

### Performance Optimization

```python
# For high-performance testing
config = {
    'browser': 'chromium',
    'headless': True,
    'launch_options': {
        'args': [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor'
        ]
    }
}
```

## Usage Examples

### Basic Navigation and Interaction

```python
async def web_test():
    runner = PlaywrightMiteRunner(config)
    
    await runner.start()
    page = await runner.new_page()
    
    # Navigate with timing
    await runner.goto(page, 'https://example.com')
    
    # Interact with elements
    await runner.click(page, '#button-id')
    await runner.fill(page, '#input-field', 'test value')
    await runner.wait_for_selector(page, '.result')
    
    # Get performance metrics
    stats = runner.get_stats()
    await runner.stop()
```

### Form Testing with Helper

```python
from mite_playwright.utils import PlaywrightPageHelper

async def form_test():
    runner = PlaywrightMiteRunner(config)
    await runner.start()
    page = await runner.new_page()
    
    helper = PlaywrightPageHelper(page)
    
    # Fill form with timing
    form_data = {
        '#username': 'testuser',
        '#password': 'password123',
        '#email': 'test@example.com'
    }
    
    metrics = await helper.fill_form(form_data, '#submit-btn')
    await runner.stop()
```

### Performance Benchmarking

```python
async def benchmark_test():
    urls = [
        'https://example.com',
        'https://httpbin.org/get',
        'https://httpbin.org/delay/1'
    ]
    
    runner = PlaywrightMiteRunner(config)
    await runner.start()
    
    for url in urls:
        page = await runner.new_page()
        metrics = await runner.goto(page, url)
        print(f"{url}: {metrics['load_time']:.2f}ms")
        await page.close()
    
    # Get comprehensive stats
    final_stats = runner.get_stats()
    await runner.stop()
```

## Integration with Mite Framework

### Scenario Pattern

```python
class PlaywrightWebScenario:
    def __init__(self):
        self.runner = PlaywrightMiteRunner({
            'browser': 'chromium',
            'headless': True
        })
    
    async def setup(self):
        await self.runner.start()
    
    async def run(self):
        page = await self.runner.new_page()
        await self.runner.goto(page, 'https://your-app.com')
        
        # Perform test actions
        await self.runner.click(page, '#login-button')
        await self.runner.fill(page, '#username', 'testuser')
        
        # Return metrics for mite
        return self.runner.get_stats()
    
    async def teardown(self):
        await self.runner.stop()
```

### Using with Mite Controller

```python
from mite import Controller

async def run_mite_test():
    controller = Controller()
    controller.add_scenario(PlaywrightWebScenario, weight=1)
    
    # Run performance test
    await controller.run()
```

## Performance Metrics

The adapter collects comprehensive performance metrics:

### Navigation Metrics
- Page load times
- Navigation timing
- Network request timing
- Response status codes

### Action Metrics  
- Click response times
- Form fill timing
- Element wait times
- Scroll performance

### Error Tracking
- Navigation failures
- Element interaction errors
- Timeout occurrences
- Network errors

### Example Stats Output

```python
{
    'navigation': {
        'count': 5,
        'avg_time': 1250.5,
        'min_time': 890.2,
        'max_time': 1580.8
    },
    'actions': {
        'clicks': {'count': 10, 'avg_time': 45.2},
        'fills': {'count': 5, 'avg_time': 32.1}
    },
    'network': {
        'requests': 25,
        'avg_time': 285.7
    },
    'errors': {'count': 0}
}
```

## Advanced Features

### Concurrent Testing

```python
async def concurrent_test():
    tasks = []
    
    for url in test_urls:
        task = test_single_url(url)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    return results
```

### Browser Pool Management

```python
# Multiple browser instances for parallel testing
runners = [
    PlaywrightMiteRunner({'browser': 'chromium'}),
    PlaywrightMiteRunner({'browser': 'firefox'}),
    PlaywrightMiteRunner({'browser': 'webkit'})
]
```

### Statistics Export

```python
# Export performance data
stats_collector = runner.stats_collector
stats_collector.export_to_csv('performance_data.csv')

# Get percentile analysis
percentiles = stats_collector.get_percentiles([50, 90, 95, 99])
```

## Comparison with Selenium Adapter

| Feature | Selenium | Playwright |
|---------|----------|------------|
| Browser Support | Chrome, Firefox, Safari | Chromium, Firefox, WebKit |
| Performance | Good | Excellent |
| API Style | Synchronous | Async/Await |
| Network Interception | Limited | Full Control |
| Mobile Testing | WebDriver | Device Emulation |
| Debugging | Standard | Rich Debugging |

## Best Practices

1. **Use Headless Mode**: For performance testing, always use headless browsers
2. **Manage Resources**: Close pages when done to free memory
3. **Handle Timeouts**: Set appropriate timeouts for your use case
4. **Monitor Metrics**: Use the stats collector to track performance trends
5. **Error Handling**: Implement proper error handling for flaky tests

## Troubleshooting

### Common Issues

1. **Browser Not Found**: Run `playwright install` to install browser binaries
2. **Import Errors**: Ensure mite_playwright is in your Python path
3. **Timeout Errors**: Increase timeout values for slow networks
4. **Memory Issues**: Close unused pages and contexts

### Debug Mode

```python
config = {
    'browser': 'chromium',
    'headless': False,  # Visible browser for debugging
    'launch_options': {
        'slowMo': 1000  # Slow down actions
    }
}
```

## Contributing

This adapter follows the same patterns as mite_selenium. When contributing:

1. Maintain async/await patterns
2. Include comprehensive error handling
3. Add performance metrics for new features
4. Update tests and documentation
5. Follow the existing code style

## License

Same license as the mite framework.