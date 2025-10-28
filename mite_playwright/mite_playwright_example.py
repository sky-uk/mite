#!/usr/bin/env python3
"""
Test script for the Playwright adapter
Validates that all components work correctly
"""

import asyncio
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


from mite_playwright import PlaywrightMiteRunner, PlaywrightStats
from mite_playwright.utils import PlaywrightPageHelper, safe_click



async def test_playwright_adapter():
    """Test the complete Playwright adapter functionality"""
        
    try:
        config = {
            'browser': 'chromium',
            'headless': False,  # Set to False to see the browser
            'timeout': 30000
        }
        
        runner = PlaywrightMiteRunner(config)
        
        # Test browser startup
        await runner.start()
        print(" Browser started successfully")
        
        # Test page creation
        page = await runner.new_page()
        print("Page created successfully")
        
        # Test navigation
        metrics = await runner.goto(page, 'https://playwright.dev/')
        print(f"Navigation completed: {metrics['load_time']:.2f}ms")
        
        # Test page helper
        helper = PlaywrightPageHelper(page)
        page_info = await helper.get_page_info()
        print(f"Page info retrieved: {page_info['title']}")
        
        # Test screenshot
        await runner.screenshot(page, 'adapter_test.png')
        print("Screenshot captured")
        
        # Test stats collection
        stats = runner.get_stats()
        print("Stats collected successfully")
        
        # Test browser cleanup
        await runner.stop()
        
        # Give a moment for async cleanup to complete
        await asyncio.sleep(0.1)
        print("Browser stopped successfully")
        
        print("\nAll tests passed! Playwright adapter is working correctly.")
        
        return True
        
    except Exception as e:
        print(f" Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_performance_comparison_journey():
    """Compare performance with different browsers"""
    print("\nPerformance Comparison Test")
    
    browsers = ['chromium', 'firefox', 'webkit']
    results = {}
    
    for browser in browsers:
        try:
            print(f"Testing {browser}...")
            
            config = {
                'browser': browser,
                'headless': False  
            }
            
            runner = PlaywrightMiteRunner(config)
            await runner.start()
            
            page = await runner.new_page()
            metrics = await runner.goto(page, 'https://playwright.dev/')
            
            results[browser] = metrics['load_time']
            print(f"{browser}: {metrics['load_time']:.2f}ms")
            
            await runner.stop()
            
            # Give time for cleanup
            await asyncio.sleep(0.1)
            
        except Exception as e:
            print(f" {browser} failed: {e}")
            results[browser] = None
            # Ensure cleanup even on error
            try:
                await runner.stop()
                await asyncio.sleep(0.1)
            except:
                pass
    
    print("\nPerformance Summary:")
    for browser, time_ms in results.items():
        if time_ms:
            print(f"  {browser}: {time_ms:.2f}ms")
        else:
            print(f"  {browser}: Failed")


def scenario():
    return [["db_folder:test_performance_comparison_journey", None, lambda s, e: 1]]



if __name__ == "__main__":
    """Main test execution"""
    print("Starting Playwright adapter tests...\n")
    
    try:
        # Run basic functionality test
        success = asyncio.run(test_playwright_adapter())
        
        if success:
            # Run performance comparison if basic test passed
            asyncio.run(test_performance_comparison_journey())
        
        print("\n" + "=" * 50)
        if success:
            print("All tests completed successfully!")
        else:
            print("Some tests failed. Check the error messages above.")
            
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
    except Exception as e:
        print(f"\nUnexpected error: {e}")