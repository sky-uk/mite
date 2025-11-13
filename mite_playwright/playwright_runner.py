import asyncio
import logging
import time
from contextlib import asynccontextmanager
from copy import deepcopy
from functools import wraps

from playwright.async_api import Page, async_playwright

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
            "browser_navigation_timeout": 30000,
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
            browser_type = getattr(
                self._playwright, self._browser_name, self._playwright.chromium
            )
            launch_options = {
                "headless": self._browser_headless,
                **(self._launch_options or {}),
                **(self._browser_options or {}),
            }
            self._browser = await browser_type.launch(**launch_options)

            # Create context with timeouts
            context_options = {
                "viewport": self._browser_viewport,
                **(self._context_options or {}),
            }
            self._browser_context = await self._browser.new_context(**context_options)
            self._browser_context.set_default_timeout(self._browser_timeout)
            self._browser_context.set_default_navigation_timeout(
                self._browser_navigation_timeout
            )

            self._context.raw_webdriver = self._browser_context

        except Exception as e:
            logger.error(f"Failed to start Playwright browser: {e}")
            await self._quit()
            raise

    async def _safe_close(self, obj, name, reset_attr=None):
        """Safely close an object with error handling"""
        if obj:
            try:
                await obj.close() if hasattr(obj, "close") else await obj.stop()
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

    async def _send_page_load_metrics(self, page: Page, response=None):
        """Send page load metrics using Playwright APIs"""
        try:
            metrics = {}

            if response and response.request.timing:
                timing = response.request.timing

                # Playwright timing uses standard Performance API property names
                dns_start = timing.get("domainLookupStart", 0)
                dns_end = timing.get("domainLookupEnd", 0)
                connect_start = timing.get("connectStart", 0)
                connect_end = timing.get("connectEnd", 0)
                secure_start = timing.get("secureConnectionStart", 0)
                request_start = timing.get("requestStart", 0)
                response_start = timing.get("responseStart", 0)
                response_end = timing.get("responseEnd", 0)

                # Calculate TLS timing
                if secure_start > 0:
                    tcp_time = (secure_start - connect_start) / 1000
                    tls_time = (connect_end - secure_start) / 1000
                else:
                    tcp_time = (connect_end - connect_start) / 1000
                    tls_time = 0

                metrics.update(
                    {
                        # Network timing  - converted to seconds
                        "dns_lookup_time": (dns_end - dns_start) / 1000,
                        "tcp_time": tcp_time,
                        "tls_time": tls_time,
                        "time_to_first_byte": (response_start - request_start) / 1000,
                        "time_to_last_byte": (response_end - request_start) / 1000,
                        "total_time": (response_end - request_start) / 1000,
                        # Request/Response timing  - converted to seconds
                        "request_start_time": request_start / 1000,
                        "response_start_time": response_start / 1000,
                        "response_end_time": response_end / 1000,
                    }
                )

            # Add response-level metrics
            if response:
                content_length = response.headers.get("content-length", "0")
                metrics.update(
                    {
                        "status_code": response.status,
                        "url": response.url,
                        "response_size": int(content_length)
                        if content_length.isdigit()
                        else 0,
                    }
                )

            if metrics:
                self._context.send("playwright_page_load_metrics", **metrics)

        except Exception as e:
            logger.error(f"Failed to collect native page load metrics: {e}")

    async def new_page(self) -> Page:
        """Create a new page and track it"""
        if not self._browser_context:
            raise MiteError("Browser context not initialized")

        page = await self._browser_context.new_page()
        self._pages.append(page)
        return page

    async def goto(self, page: Page, url: str, **options):
        """Navigate page to URL with options"""
        response = await page.goto(url, **options)
        await self._send_page_load_metrics(page, response)
        return response

    async def login(
        self,
        page: Page,
        login_url: str,
        username: str,
        password: str,
        username_selector: str = "input[name='username']",
        password_selector: str = "input[name='password']",
        submit_selector: str = "button[type='submit']",
        success_url_pattern: str = None,
        timeout: int = 30000,
        **options,
    ):
        """
        Playwright login with automatic metrics collection
        """
        try:
            # Navigate to login page with metrics
            await self.goto(page, login_url)
            await page.wait_for_selector(username_selector, timeout=timeout)

            # Fill login credentials
            await page.fill(username_selector, username, **options)
            await page.fill(password_selector, password, **options)
            await page.click(submit_selector, **options)

            # Wait for navigation/redirect after login
            if success_url_pattern:
                await page.wait_for_url(success_url_pattern, timeout=timeout)
            else:
                await page.wait_for_load_state("networkidle", timeout=timeout)

            # Collect metrics after successful login
            await self._send_page_load_metrics(page)

            return page

        except Exception as e:
            raise MiteError(
                f"Login failed for user '{username}' at '{login_url}': {str(e)}"
            )

    def get_playwright_metrics_context(self, page: Page = None):
        """Get Playwright metrics context"""
        page = self._get_page(page)
        return PlaywrightMetricsContext(self, page)

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


class PlaywrightMetricsContext:
    def __init__(self, browser_wrapper, page: Page):
        self._browser = browser_wrapper
        self._page = page
        self.responses = []
        self.start_time = None
        self.execution_time = None
        self._response_handler = None

    async def __aenter__(self):
        self.start_time = time.time()

        # Set up response listener for metrics
        def on_response(response):
            self.responses.append(
                {
                    "url": response.url,
                    "status": response.status,
                    "timing": response.request.timing,
                    "size": len(str(response.headers.get("content-length", "0"))),
                }
            )

        # Store the handler so we can remove it later
        self._response_handler = on_response
        self._page.on("response", self._response_handler)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.execution_time = time.time() - self.start_time
        # Remove response listener
        try:
            self._page.remove_listener("response", self._response_handler)
        except Exception as e:
            logger.warning(f"Error removing response listener: {e}")


class _PlaywrightWireWrapper(_PlaywrightWrapper):
    """Wrapper that provides network interception capabilities"""

    def __init__(self, context):
        super().__init__(context)
        self._network_options = self._spec_import_if_not_none("network_options") or {}
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
        self._requests.append(
            {
                "url": request.url,
                "method": request.method,
                "headers": request.headers,
                "timestamp": time.time(),
                "type": "request",
            }
        )

    def _on_response(self, response):
        """Track incoming responses"""
        self._requests.append(
            {
                "url": response.url,
                "status": response.status,
                "headers": response.headers,
                "timestamp": time.time(),
                "type": "response",
            }
        )

    async def _route_handler(self, route):
        """Handle route interception"""
        modified_request = (
            self._request_interceptor(route.request)
            if self._request_interceptor
            else None
        )
        await route.continue_(
            **modified_request
        ) if modified_request else await route.continue_()

    async def wait_for_request(self, url_pattern, timeout=5000):
        start_time = time.time()

        while time.time() - start_time < timeout / 1000:
            for req in self._requests:
                if req["type"] == "request" and url_pattern in req["url"]:
                    return req
            await asyncio.sleep(0.1)

        raise MiteError(f"Timeout waiting for request matching '{url_pattern}'")

    @property
    def requests(self):
        return [req for req in self._requests if req["type"] == "request"]

    def add_request_interceptor(self, request_interceptor):
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
