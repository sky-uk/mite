import asyncio
import logging
import time
from contextlib import asynccontextmanager
from copy import deepcopy
from functools import wraps

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from mite.exceptions import MiteError
from mite.utils import spec_import

logger = logging.getLogger(__name__)


class _PlaywrightWrapper:
    def __init__(self, context):
        """Constructor pulls capabilities and other browser config from the context"""
        self._context = context
        
        # Browser configuration with defaults
        config_defaults = {
            "browser_name": "chromium",
            "browser_headless": True, 
            "browser_viewport": {"width": 1280, "height": 720},
            "browser_timeout": 30000,
            "browser_navigation_timeout": 30000
        }
        
        for key, default in config_defaults.items():
            setattr(self, f"_{key}", self._context.config.get(key, default))
        
        # Advanced options via spec_import
        for option in ["browser_options", "context_options", "launch_options"]:
            value = self._context.config.get(option)
            setattr(self, f"_{option}", deepcopy(spec_import(value)) if value else None)
        
        # Internal state
        self._playwright = self._browser = self._browser_context = None
        self._pages = []

    async def _start(self):
        """Start Playwright browser and set up context"""
        try:
            self._context.browser = self
            self._playwright = await async_playwright().start()
            
            # Get browser type and launch
            browser_type = getattr(self._playwright, self._browser_name, self._playwright.chromium)
            launch_options = {"headless": self._browser_headless, 
                            **(self._launch_options or {}), **(self._browser_options or {})}
            self._browser = await browser_type.launch(**launch_options)
            
            # Create context with timeouts
            context_options = {"viewport": self._browser_viewport, **(self._context_options or {})}
            self._browser_context = await self._browser.new_context(**context_options)
            self._browser_context.set_default_timeout(self._browser_timeout)
            self._browser_context.set_default_navigation_timeout(self._browser_navigation_timeout)
            
            self._context.raw_webdriver = self._browser_context
            
        except Exception as e:
            logger.error(f"Failed to start Playwright browser: {e}")
            await self._quit()
            raise

    async def _safe_close(self, obj, name, reset_attr=None):
        """Safely close an object with error handling"""
        if obj:
            try:
                await obj.close() if hasattr(obj, 'close') else await obj.stop()
            except Exception as e:
                logger.warning(f"Error closing {name}: {e}")
            if reset_attr:
                setattr(self, reset_attr, None)

    async def _quit(self):
        """Clean up Playwright resources"""
        try:
            # Close pages
            for page in self._pages[:]:
                await self._safe_close(page, "page")
            self._pages.clear()
            
            # Close context, browser, and stop Playwright
            await self._safe_close(self._browser_context, "context", "_browser_context")
            await self._safe_close(self._browser, "browser", "_browser")
            await self._safe_close(self._playwright, "playwright", "_playwright")
                
        except Exception as e:
            logger.error(f"Error during Playwright cleanup: {e}")

    def _get_page(self, page: Page = None) -> Page:
        """Get page instance with automatic fallback to first available page"""
        if page is None:
            page = self._pages[0] if self._pages else None
        if page is None:
            raise MiteError("No page available")
        return page

    def _browser_has_timing_capabilities(self):
        """All modern browsers support performance timing"""
        return True

    def _calculate_timings(self, timings):
        """Calculate TCP and TLS timing based on connection type"""
        is_tls = timings["name"].startswith("https")
        
        if is_tls:
            tcp_time = timings["secureConnectionStart"] - timings["connectStart"] 
            tls_time = timings["connectEnd"] - timings["secureConnectionStart"]
        else:
            tcp_time = timings["connectEnd"] - timings["connectStart"]
            tls_time = 0
            if tls_time == 0:
                logger.info("Secure TLS connection not used, defaulting tls_time to 0")
        
        return tcp_time, tls_time

    async def _send_page_load_metrics(self, page: Page):
        """Send page load metrics to mite context"""
        if not self._browser_has_timing_capabilities():
            return
            
        try:
            # Get performance entries
            performance_entries = await page.evaluate("""
                () => performance.getEntriesByType('navigation')
            """)

            paint_entries = await page.evaluate("""
                () => performance.getEntriesByType('paint')
            """)

            _timings = self._extract_entries(performance_entries)
            timings = _timings[0] if _timings else None
            
            if timings:
                protocol = timings.get("nextHopProtocol")
                if protocol and protocol != "http/1.1":
                    logger.warning(
                        f"Timings may be inaccurate as protocol is not http/1.1: {protocol}"
                    )
                tcp_time, tls_time = self._calculate_timings(timings)
                metrics = {
                    "dns_lookup_time": timings["domainLookupEnd"] - timings["domainLookupStart"],
                    "dom_interactive": timings["domInteractive"],
                    "js_onload_time": timings["domContentLoadedEventEnd"] - timings["domContentLoadedEventStart"],
                    "page_weight": timings.get("transferSize", 0),
                    "render_time": timings["domInteractive"] - timings["responseEnd"],
                    "tcp_time": tcp_time,
                    "time_to_first_byte": timings["responseStart"] - timings["connectEnd"],
                    "time_to_interactive": timings["domInteractive"] - timings["requestStart"],
                    "time_to_last_byte": timings["responseEnd"] - timings["connectEnd"],
                    "tls_time": tls_time,
                    "total_time": timings["duration"],
                }
            else:
                metrics = {}

            _paint_timings = self._extract_entries(paint_entries, expected=2)
            paint_timings = (
                self._format_paint_timings(_paint_timings) if _paint_timings else None
            )
            if paint_timings:
                metrics["first_contentful_paint"] = paint_timings.get("first-contentful-paint", 0)
                metrics["first_paint"] = paint_timings.get("first-paint", 0)

            if metrics:
                self._context.send(
                    "playwright_page_load_metrics",
                    **self._extract_and_convert_metrics_to_seconds(metrics),
                )
                
        except Exception as e:
            logger.error(f"Failed to collect page load metrics: {e}")

    def _extract_entries(self, entries, expected=1):
        if len(entries) == expected:
            return entries[:expected]
        logger.error(
            f"Performance entries did not return the expected count: expected {expected} - actual {len(entries)}"
        )
        return

    def _format_paint_timings(self, entries):
        return {metric["name"]: metric["startTime"] for metric in entries}

    def _extract_and_convert_metrics_to_seconds(self, metrics):
        converted_metrics = {}
        non_time_based_metrics = ["page_weight", "resource_path"]
        for k, v in metrics.items():
            if k not in non_time_based_metrics:
                converted_metrics[k] = self._convert_ms_to_seconds(v)
            else:
                converted_metrics[k] = v
        return converted_metrics

    def _convert_ms_to_seconds(self, value_ms):
        return value_ms / 1000

    async def _retrieve_javascript_metrics(self, page: Page):
        try:
            return await page.evaluate("""
                () => performance.getEntriesByType('resource')
            """)
        except Exception:
            logger.error("Failed to retrieve resource performance entries")
            return []

    async def _clear_resource_timings(self, page: Page):
        try:
            await page.evaluate("() => performance.clearResourceTimings()")
        except Exception as e:
            logger.error(f"Failed to clear resource timings: {e}")

    async def new_page(self) -> Page:
        """Create a new page and track it"""
        if not self._browser_context:
            raise MiteError("Browser context not initialized")
            
        page = await self._browser_context.new_page()
        self._pages.append(page)
        return page

    async def get(self, url, page: Page = None):
        """Navigate to URL and send metrics (Selenium-style interface)"""
        if page is None:
            if not self._pages:
                page = await self.new_page()
            else:
                page = self._pages[0]
                
        await page.goto(url)
        await self._send_page_load_metrics(page)
        return page

    async def goto(self, page: Page, url: str, **options):
        """Navigate page to URL with options"""
        response = await page.goto(url, **options)
        await self._send_page_load_metrics(page)
        return response

    def get_js_metrics_context(self, page: Page = None):
        """Get JavaScript metrics context"""
        page = self._get_page(page)
        return JsMetricsContext(self, page)

    async def wait_for_elements(self, locator, timeout=5000, page: Page = None):
        """Wait for elements to be present"""
        page = self._get_page(page)
        
        try:
            return await page.wait_for_selector(locator, timeout=timeout, state="attached")
        except Exception as e:
            raise MiteError(f"Timed out trying to find elements '{locator}' in the dom") from e

    async def wait_for_element(self, locator, timeout=5000, page: Page = None):
        """Wait for element to be present"""
        page = self._get_page(page)
        
        try:
            return await page.wait_for_selector(locator, timeout=timeout)
        except Exception as e:
            raise MiteError(f"Timed out trying to find element '{locator}' in the dom") from e

    async def wait_for_url(self, url_pattern, timeout=5000, page: Page = None):
        """Wait for URL to match pattern"""
        page = self._get_page(page)
        
        try:
            await page.wait_for_url(url_pattern, timeout=timeout)
            return True
        except Exception as e:
            raise MiteError(f"Timed out waiting for url to be '{url_pattern}'") from e

    async def switch_to_default(self, page: Page = None):
        page = self._get_page(page)
        # In Playwright, we can access the main frame directly
        return page.main_frame

    async def switch_to_iframe(self, locator, page: Page = None):
        page = self._get_page(page)
        element = await page.wait_for_selector(locator)
        frame = await element.content_frame()
        return frame

    def current_url(self, page: Page = None):
        """Get current URL (Selenium-style interface)"""
        page = self._get_page(page)
        return page.url

    async def click(self, locator, page: Page = None, **options):
        """Click element by locator (Selenium-style interface)"""
        page = self._get_page(page)
        
        try:
            await page.click(locator, **options)
            # Send metrics after click in case it triggers navigation
            await self._send_page_load_metrics(page)
        except Exception as e:
            raise MiteError(f"Failed to click element '{locator}'") from e

    async def fill(self, locator, value, page: Page = None, **options):
        """Fill input element with value (Selenium-style interface)"""
        page = self._get_page(page)
        
        try:
            await page.fill(locator, value, **options)
        except Exception as e:
            raise MiteError(f"Failed to fill element '{locator}' with value '{value}'") from e


    async def login(self, login_url, username, password, 
                   username_locator="username", password_locator="password", 
                   submit_locator="button[type='submit']", page: Page = None,
                   wait_for_redirect=True, success_url_pattern=None, **options):
        """Perform login with automatic form handling and metrics collection"""
        page = page or await self.new_page() if not self._pages else self._pages[0]
        
        try:
            await self.get(login_url, page)
            await page.wait_for_selector(username_locator, timeout=self._browser_timeout)
            await page.fill(username_locator, username, **options)
            await page.fill(password_locator, password, **options)
            await page.click(submit_locator, **options)
            
            if wait_for_redirect:
                if success_url_pattern:
                    await page.wait_for_url(success_url_pattern, timeout=self._browser_navigation_timeout)
                else:
                    await page.wait_for_load_state('networkidle', timeout=self._browser_navigation_timeout)
                await self._send_page_load_metrics(page)
            
            return page
            
        except Exception as e:
            raise MiteError(f"Failed to login at '{login_url}' with username '{username}'") from e


    @property
    def pages(self):
        """Get all open pages"""
        return self._pages.copy()

    @property
    def context(self):
        """Get browser context"""
        return self._browser_context

    @property
    def browser(self):
        """Get browser instance"""
        return self._browser


class JsMetricsContext:
    def __init__(self, browser_wrapper, page: Page):
        self._browser = browser_wrapper
        self._page = page
        self.results = None
        self.start_time = None
        self.execution_time = None

    async def __aenter__(self):
        self.start_time = time.time()
        await self._browser._clear_resource_timings(self._page)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.results = await self._browser._retrieve_javascript_metrics(self._page)
        self.execution_time = time.time() - self.start_time


class _PlaywrightWireWrapper(_PlaywrightWrapper):
    """Wrapper that provides network interception capabilities similar to Selenium Wire"""
    
    def __init__(self, context):
        super().__init__(context)
        self._network_options = (
            self._spec_import_if_not_none("network_options") or {}
        )
        self._requests = []
        self._request_interceptor = None

    async def _start(self):
        """Start with network interception enabled"""
        await super()._start()
        
        # Enable network tracking
        if self._browser_context:
            # Track all requests
            self._browser_context.on("request", self._on_request)
            self._browser_context.on("response", self._on_response)
            
            # Set up route interception if interceptor is provided
            if self._request_interceptor:
                await self._browser_context.route("**/*", self._route_handler)

    def _on_request(self, request):
        """Track outgoing requests"""
        self._requests.append({
            "url": request.url,
            "method": request.method,
            "headers": request.headers,
            "timestamp": time.time(),
            "type": "request"
        })

    def _on_response(self, response):
        """Track incoming responses"""
        self._requests.append({
            "url": response.url,
            "status": response.status,
            "headers": response.headers,
            "timestamp": time.time(),
            "type": "response"
        })

    async def _route_handler(self, route):
        """Handle route interception"""
        request = route.request
        
        if self._request_interceptor:
            # Call interceptor
            modified_request = self._request_interceptor(request)
            if modified_request:
                # Continue with modified request
                await route.continue_(**modified_request)
            else:
                await route.continue_()
        else:
            await route.continue_()

    async def wait_for_request(self, url_pattern, timeout=5000):
        """Wait for a request matching URL pattern (Selenium Wire style)"""
        start_time = time.time()
        
        while time.time() - start_time < timeout / 1000:
            for req in self._requests:
                if req["type"] == "request" and url_pattern in req["url"]:
                    return req
            await asyncio.sleep(0.1)
            
        raise MiteError(f"Timeout waiting for request matching '{url_pattern}'")

    @property
    def requests(self):
        """Get all tracked requests (Selenium Wire style)"""
        return [req for req in self._requests if req["type"] == "request"]

    def add_request_interceptor(self, request_interceptor):
        """Add request interceptor (Selenium Wire style)"""
        self._request_interceptor = request_interceptor


@asynccontextmanager
async def _playwright_context_manager(context, wire):
    """Context manager for Playwright browser lifecycle"""
    pw = _PlaywrightWireWrapper(context) if wire else _PlaywrightWrapper(context)
    try:
        await pw._start()
        yield
    finally:
        await pw._quit()


def mite_playwright(*args, wire=False):
    """
    Decorator for Playwright-based mite test functions.
    Usage:
        @mite_playwright
        async def test_function(ctx):
            page = await ctx.browser.new_page()
            await ctx.browser.get("https://example.com", page)
    """
    def wrapper_factory(func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            async with _playwright_context_manager(ctx, wire):
                return await func(ctx, *args, **kwargs)

        return wrapper

    if len(args) == 0:
        return wrapper_factory
    elif len(args) > 1:
        raise Exception("Anomalous invocation of mite_playwright decorator")
    else:
        return wrapper_factory(args[0])