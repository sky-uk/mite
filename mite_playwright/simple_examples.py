"""
Simple examples for mite Playwright adapter
"""

import asyncio
from . import SimplePlaywrightRunner, SimplePlaywrightScenario, SimplePageLoadScenario


class SimpleECommerceScenario(SimplePlaywrightScenario):
    """Simple e-commerce test scenario"""
    
    def __init__(self, runner, shop_url):
        super().__init__(runner, "ecommerce")
        self.shop_url = shop_url
    
    async def execute(self):
        """Simple e-commerce flow"""
        # Navigate to shop
        nav_time = await self.runner.goto(self.shop_url)
        self.log_metric("shop_load_time", nav_time)
        
        # Search for product
        search_time = await self.runner.fill("#search", "laptop")
        self.log_metric("search_fill_time", search_time)
        
        # Click search button
        search_click_time = await self.runner.click("#search-button")
        self.log_metric("search_click_time", search_click_time)
        
        # Wait for results
        results_time = await self.runner.wait_for(".search-results")
        self.log_metric("results_load_time", results_time)


async def run_simple_examples():
    """Run simple examples"""
    runner = SimplePlaywrightRunner(headless=True)
    
    # Example 1: Simple page load
    print("=== Page Load Test ===")
    page_scenario = SimplePageLoadScenario(runner, "https://example.com")
    await page_scenario.run()
    
    print("\n=== E-commerce Test ===")
    ecommerce_scenario = SimpleECommerceScenario(runner, "https://shop.example.com")
    await ecommerce_scenario.run()


if __name__ == "__main__":
    asyncio.run(run_simple_examples())