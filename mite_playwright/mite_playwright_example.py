"""
Mite Playwright Example with Metrics Visualization

"""

import asyncio
import time
from playwright_runner import mite_playwright


class MockContext:
    def __init__(self):
        self.config = {
            "browser_name": "chromium", 
            "browser_headless": False,  # Set to False to see browser actions
            "browser_viewport": {"width": 1280, "height": 720},
            "browser_timeout": 30000,
        }
        self.browser = None
        self.raw_webdriver = None
        self.collected_metrics = []
        
    def send(self, metric_name, **kwargs):
        """Enhanced send method to display metrics in real-time"""
        print(f"\nMETRIC COLLECTED: {metric_name}")
        print("=" * 50)
        for key, value in kwargs.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.4f}s")
            else:
                print(f"  {key}: {value}")
        
        # Store metrics for later analysis
        self.collected_metrics.append({
            "name": metric_name,
            "data": kwargs,
            "timestamp": time.time()
        })
        
    def show_metrics_summary(self):
        """Display a comprehensive summary of all collected metrics"""
        if not self.collected_metrics:
            print(" No metrics collected.")
            return
            
        print("\n METRICS SUMMARY")
        print("=" * 60)
        
        for i, metric in enumerate(self.collected_metrics, 1):
            print(f"\nMetric #{i}: {metric['name']}")
            print(f"Timestamp: {time.strftime('%H:%M:%S', time.localtime(metric['timestamp']))}")
            
            # Show key performance indicators
            data = metric['data']
            metrics_labels = {
                'total_time': "Total Page Load Time",
                'dns_lookup_time': "DNS Lookup", 
                'time_to_first_byte': "⚡ Time to First Byte",
                'dom_interactive': "DOM Interactive",
                'first_contentful_paint':  "First Contentful Paint",
                'first_paint': "First Paint",
                'render_time': "Render Time", 
                'tcp_time': "TCP Connect Time",
                'tls_time': "TLS Handshake Time",
                'page_weight': "Page Weight"
            }
            
            for key, label in metrics_labels.items():
                if key in data:
                    if key == 'page_weight':
                        print(f"{label}: {data[key]} bytes")
                    else:
                        print(f"{label}: {data[key]:.4f}s")
                
        print("\n" + "=" * 60)



@mite_playwright(wire=True)
async def metrics_demo_network_tracking(ctx):
    """Demonstrate network request tracking with wire=True"""
    print("\n Starting Network Tracking Demo...")
    page = await ctx.browser.new_page()
    # Navigate and automatically track network requests
    await ctx.browser.get("https://httpbin.org/json", page)
    
    # Show tracked requests
    requests = ctx.browser.requests
    print(f"Total network requests tracked: {len(requests)}")
    
    if requests:
        print("\n Network Requests:")
        for i, req in enumerate(requests[:3], 1):  # Show first 3
            print(f"  {i}. {req['method']} {req['url']}")


async def main():
    """Main function demonstrating metrics visualization"""
    print("Mite Playwright Metrics Examples")
    print("=" * 50)
    
    ctx = MockContext()
    try:        
        print("\nNetwork Tracking Test")
        await metrics_demo_network_tracking(ctx)
        
    except Exception as e:
        print(f" Error during execution: {e}")
    
    ctx.show_metrics_summary()


if __name__ == "__main__":
    asyncio.run(main())