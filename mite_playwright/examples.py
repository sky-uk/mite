"""
Playwright Examples for Mite Framework

Example usage patterns for the Playwright adapter in mite framework.
Shows how to use the adapter for performance testing scenarios.
"""

import asyncio
import logging
from typing import Dict, Any

# Handle both relative imports (when used as package) and direct execution
try:
    from .runner import PlaywrightMiteRunner
    from .utils import PlaywrightPageHelper, format_timing_stats
except ImportError:
    # If relative imports fail, try absolute imports for direct execution
    from runner import PlaywrightMiteRunner
    from utils import PlaywrightPageHelper, format_timing_stats

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def basic_navigation_example():
    """
    Basic navigation example using Playwright adapter.
    Similar to Selenium examples but with Playwright.
    """
    config = {
        'browser': 'chromium',
        'headless': False,  # Set to False to see the browser
        'timeout': 30000
    }
    
    runner = PlaywrightMiteRunner(config)
    
    try:
        # Start browser
        await runner.start()
        logger.info("Browser started successfully")
        
        # Create new page
        page = await runner.new_page()
        
        # Navigate to website
        metrics = await runner.goto(page, 'https://playwright.dev/')
        logger.info(f"Navigation completed: {metrics}")
        
        # Take screenshot
        await runner.screenshot(page, 'example_page.png')
        logger.info("Screenshot taken")
        
        # Get page stats
        stats = runner.get_stats()
        logger.info("Performance stats collected")
        
        return stats
        
    except Exception as e:
        logger.error(f"Example failed: {e}")
        raise
    finally:
        await runner.stop()
        logger.info("Browser stopped")


async def form_interaction_example():
    """
    Form interaction example with timing measurement.
    """
    config = {
        'browser': 'chromium',
        'headless': False,  # Visible for demonstration
        'context_options': {
            'viewport': {'width': 1280, 'height': 720}
        }
    }
    
    runner = PlaywrightMiteRunner(config)
    
    try:
        await runner.start()
        page = await runner.new_page()
        
        # Navigate to form page
        await runner.goto(page, 'https://playwright.dev/')
        
        # Use page helper for form operations
        helper = PlaywrightPageHelper(page)
        
        # Fill form with timing
        form_data = {
            'input[name="custname"]': 'John Doe',
            'input[name="custtel"]': '555-1234',
            'input[name="custemail"]': 'john@example.com',
            'textarea[name="comments"]': 'Test comment for performance testing'
        }
        
        form_metrics = await helper.fill_form(form_data, 'input[type="submit"]')
        logger.info(f"Form interaction metrics: {form_metrics}")
        
        # Wait for result page
        await page.wait_for_timeout(2000)
        
        # Get final stats
        stats = runner.get_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Form example failed: {e}")
        raise
    finally:
        await runner.stop()


async def login_scenario_example():
    """
    Login scenario example with performance measurement.
    """
    config = {
        'browser': 'firefox',  # Test with different browser
        'headless': True
    }
    
    runner = PlaywrightMiteRunner(config)
    
    try:
        await runner.start()
        page = await runner.new_page()
        
        # Navigate to login page (using httpbin for demo)
        await runner.goto(page, 'https://playwright.dev/')
        
        # Simulate login steps
        helper = PlaywrightPageHelper(page)
        
        # For basic auth, we'll just measure navigation
        # In real scenario, you'd have form fields
        page_info = await helper.get_page_info()
        logger.info(f"Page info: {page_info}")
        
        # Measure some interactions
        await runner.click(page, 'body')  # Click somewhere safe
        await page.wait_for_timeout(1000)
        
        stats = runner.get_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Login example failed: {e}")
        raise
    finally:
        await runner.stop()


async def performance_benchmark_example():
    """
    Performance benchmarking example with multiple pages.
    """
    config = {
        'browser': 'chromium',
        'headless': True
    }
    
    urls_to_test = [
        'https://playwright.dev/',
    ]
    
    runner = PlaywrightMiteRunner(config)
    
    try:
        await runner.start()
        
        for url in urls_to_test:
            logger.info(f"Testing {url}")
            
            page = await runner.new_page()
            
            # Navigate and measure
            metrics = await runner.goto(page, url)
            logger.info(f"Load time for {url}: {metrics['load_time']:.2f}ms")
            
            # Take screenshot for verification
            screenshot_name = f"benchmark_{url.replace('/', '_').replace(':', '')}.png"
            await runner.screenshot(page, screenshot_name)
            
            # Close page to free memory
            await page.close()
            
        # Get comprehensive stats
        final_stats = runner.get_stats()
        
        # Format and display results
        formatted_stats = format_timing_stats(final_stats)
        logger.info(f"\nFinal Performance Results:\n{formatted_stats}")
        
        return final_stats
        
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        raise
    finally:
        await runner.stop()


async def concurrent_testing_example():
    """
    Example of concurrent testing with multiple runner instances.
    """
    async def test_single_url(url: str, browser: str = 'chromium') -> Dict[str, Any]:
        """Test a single URL with its own runner instance"""
        config = {
            'browser': browser,
            'headless': True
        }
        
        runner = PlaywrightMiteRunner(config)
        
        try:
            await runner.start()
            page = await runner.new_page()
            
            metrics = await runner.goto(page, url)
            stats = runner.get_stats()
            
            return {
                'url': url,
                'browser': browser,
                'load_time': metrics['load_time'],
                'stats': stats
            }
            
        finally:
            await runner.stop()
    
    # Test multiple URLs concurrently
    urls = [
        'https://playwright.dev/',
    ]
    
    # Create concurrent tasks
    tasks = []
    for i, url in enumerate(urls):
        browser = ['chromium', 'firefox', 'webkit'][i % 3]  # Rotate browsers
        task = test_single_url(url, browser)
        tasks.append(task)
    
    # Run all tasks concurrently
    results = await asyncio.gather(*tasks)
    
    # Analyze results
    logger.info("Concurrent testing results:")
    for result in results:
        logger.info(f"{result['url']} ({result['browser']}): {result['load_time']:.2f}ms")
    
    return results


def mite_scenario_example():
    """
    Example of how to integrate with mite scenarios.
    This shows the pattern for using Playwright in mite test scenarios.
    """
    
    class PlaywrightWebTestScenario:
        """Example mite scenario using Playwright"""
        
        def __init__(self):
            self.config = {
                'browser': 'chromium',
                'headless': True
            }
            self.runner = None
            
        async def setup(self):
            """Setup phase - initialize browser"""
            self.runner = PlaywrightMiteRunner(self.config)
            await self.runner.start()
            
        async def run(self):
            """Main test execution"""
            page = await self.runner.new_page()
            
            # Perform test actions
            await self.runner.goto(page, 'https://playwright.dev/')
            await self.runner.click(page, 'body')
            
            # Return metrics for mite
            return self.runner.get_stats()
            
        async def teardown(self):
            """Cleanup phase"""
            if self.runner:
                await self.runner.stop()
    
    return PlaywrightWebTestScenario


# Example usage functions
async def run_all_examples():
    """Run all example scenarios"""
    logger.info("Running Playwright adapter examples...")
    
    try:
        # Basic navigation
        logger.info("\n1. Basic Navigation Example")
        await basic_navigation_example()
        
        # Form interaction
        logger.info("\n2. Form Interaction Example")
        await form_interaction_example()
        
        # Login scenario
        logger.info("\n3. Login Scenario Example")
        await login_scenario_example()
        
        # Performance benchmark
        logger.info("\n4. Performance Benchmark Example")
        await performance_benchmark_example()
        
        # Concurrent testing
        logger.info("\n5. Concurrent Testing Example")
        await concurrent_testing_example()
        
        logger.info("\nAll examples completed successfully!")
        
    except Exception as e:
        logger.error(f"Examples failed: {e}")
        raise


if __name__ == "__main__":
    # Run examples when module is executed directly
    asyncio.run(run_all_examples())