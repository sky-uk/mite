"""
Simple Mite Playwright Example - Getting Metrics
"""
import asyncio

from playwright_runner import mite_playwright


# Mock context for standalone testing
class MockContext:
    def __init__(self):
        self.config = {
            "browser_name": "chromium",
            "browser_headless": True,  # Set to False to see browser
        }

    def send(self, metric_name, **kwargs):
        print(f" METRIC: {metric_name}")
        for key, value in kwargs.items():
            if isinstance(value, float):
                print(f"   {key}: {value:.4f}")
            else:
                print(f"   {key}: {value}")


@mite_playwright
async def simple_page_test(ctx):
    """Simple test that collects metrics automatically"""

    try:
        # Create a new page
        page = await ctx.browser.new_page()

        # Navigate to a page - metrics are collected automatically
        response = await ctx.browser.goto(page, "https://httpbin.org/get")

        print(f"Status: {response.status}")
        print(f"URL: {response.url}")

        # Interact with the page
        await page.wait_for_load_state("networkidle")

        print("Test completed - metrics sent to mite automatically")

    except Exception as e:
        print(f" Simple page test error: {e}")


if __name__ == "__main__":

    ctx = MockContext()
    asyncio.run(simple_page_test(ctx))
