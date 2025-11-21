"""
mite example with metrics
"""

import asyncio

from __init__ import mite_playwright


@mite_playwright
async def simple_navigation_test(ctx, playwright):
    """Simple navigation test - automatically captures metrics for any response"""
    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()
    await page.goto("https://example.com")
    await browser.close()
    print("Test completed!")


# Mock context for standalone testing
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
        print()


if __name__ == "__main__":

    ctx = MockContext()
    asyncio.run(simple_navigation_test(ctx))
