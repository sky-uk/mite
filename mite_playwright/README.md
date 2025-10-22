# Simple Playwright Adapter for Mite

A lightweight browser automation adapter using Playwright for the mite performance testing framework.

## Quick Start

### Installation

```bash
pip install playwright
playwright install
```

### Basic Usage

```python
import asyncio
from mite_playwright import SimplePlaywrightRunner, SimplePlaywrightScenario

class MyTest(SimplePlaywrightScenario):
    async def execute(self):
        # Navigate and measure timing
        load_time = await self.runner.goto("https://example.com")
        self.log_metric("page_load", load_time)
        
        # Click button and measure
        click_time = await self.runner.click("#button")
        self.log_metric("button_click", click_time)

async def run_test():
    runner = SimplePlaywrightRunner(headless=True)
    scenario = MyTest(runner, "my_test")
    await scenario.run()

asyncio.run(run_test())
```

## Built-in Scenarios

### Page Load Test
```python
from mite_playwright import SimplePageLoadScenario

runner = SimplePlaywrightRunner()
scenario = SimplePageLoadScenario(runner, "https://example.com")
await scenario.run()
```

### Login Test
```python
from mite_playwright import SimpleLoginScenario

runner = SimplePlaywrightRunner()
scenario = SimpleLoginScenario(
    runner, 
    "https://example.com/login", 
    "username", 
    "password"
)
await scenario.run()
```

## API Reference

### SimplePlaywrightRunner

- `__init__(headless=True, browser_type="chromium")` - Create runner
- `start()` - Start browser
- `stop()` - Stop browser  
- `goto(url)` - Navigate to URL, returns timing
- `click(selector)` - Click element, returns timing
- `fill(selector, text)` - Fill input, returns timing
- `wait_for(selector)` - Wait for element, returns timing
- `get_text(selector)` - Get element text
- `screenshot(path)` - Take screenshot

### SimplePlaywrightScenario

- `__init__(runner, name)` - Create scenario
- `run()` - Execute full scenario
- `execute()` - Override with test steps
- `log_metric(name, value)` - Log performance metric

## Examples

See `simple_examples.py` for more examples including e-commerce scenarios.