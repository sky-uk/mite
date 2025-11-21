"""
Mite Playwright - Simple async wrapper with automatic navigation metrics
"""
import logging
from functools import wraps

from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


class PlaywrightWrapper:
    """Simple wrapper for Playwright objects"""

    def __init__(self, wrapped_obj, context):
        self._wrapped = wrapped_obj
        self._context = context

    def __getattr__(self, name):
        """Intercept all attribute access"""
        attr = getattr(self._wrapped, name)

        # Wrap callables, wrap objects that have methods, return primitives as-is
        return (
            self._wrap_method(attr)
            if callable(attr)
            else PlaywrightWrapper(attr, self._context)
            if hasattr(attr, "__dict__")
            else attr
        )

    def _wrap_method(self, method):
        """Wrap a method with error handling and metrics"""

        @wraps(method)
        async def async_wrapper(*args, **kwargs):
            try:
                result = await method(*args, **kwargs)

                # Send metrics for any method that returns a response object
                if result and hasattr(result, "request") and hasattr(result, "status"):
                    await collect_metrics(result, self._context)

                # Wrap result if it has methods (likely a complex object)
                if hasattr(result, "__dict__"):
                    return PlaywrightWrapper(result, self._context)
                return result
            except Exception as e:
                self._context.send(
                    "playwright_error", method=method.__name__, error=str(e)
                )
                raise

        return async_wrapper


async def collect_metrics(response, context):
    """Collect all metrics in one function"""
    try:
        # Navigation metrics
        metrics = {"url": response.url, "status": response.status}

        # Timing metrics if available
        if response.request and response.request.timing:
            timing = response.request.timing

            # Extract timing data
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
                    # Network timing - converted to seconds
                    "dns_lookup_time": (dns_end - dns_start) / 1000,
                    "tcp_time": tcp_time,
                    "tls_time": tls_time,
                    "time_to_first_byte": (response_start - request_start) / 1000,
                    "time_to_last_byte": (response_end - request_start) / 1000,
                    "total_time": (response_end - request_start) / 1000,
                    # Request/Response timing - converted to seconds
                    "request_start_time": request_start / 1000,
                    "response_start_time": response_start / 1000,
                    "response_end_time": response_end / 1000,
                }
            )

        # Add response size
        content_length = response.headers.get("content-length", "0")
        metrics["response_size"] = int(content_length) if content_length.isdigit() else 0

        context.send("playwright_page_load_metrics", **metrics)

        # Paint metrics if page available
        if hasattr(response, "frame") and hasattr(response.frame, "page"):
            page = response.frame.page

            # Wait for paint events to be available
            await page.wait_for_timeout(500)

            paint_data = await page.evaluate(
                """
                () => {
                    const result = {};
                    const nav = performance.getEntriesByType('navigation')[0];
                    // Paint metrics
                    performance.getEntriesByType('paint').forEach(entry => {
                        if (entry.name === 'first-paint') {
                            result.first_paint = entry.startTime / 1000;
                        } else if (entry.name === 'first-contentful-paint') {
                            result.first_contentful_paint = entry.startTime / 1000;
                        }
                    });
                    // Advanced metrics from navigation timing
                    if (nav) {
                        result.js_onload_time = (nav.loadEventEnd - nav.navigationStart) / 1000;
                        result.render_time = (nav.loadEventEnd - nav.responseEnd) / 1000;
                        result.time_to_interactive = (nav.domInteractive - nav.navigationStart) / 1000;
                        // Page weight - sum of all resource transfer sizes
                        let totalSize = nav.transferSize || 0;
                        performance.getEntriesByType('resource').forEach(resource => {
                            totalSize += resource.transferSize || 0;
                        });
                        result.page_weight = totalSize;
                        }
                    return result;
                }
            """
            )

            if paint_data:
                context.send("playwright_paint_metrics", **paint_data)

    except Exception as e:
        logger.warning(f"Metrics collection failed: {e}")


def mite_playwright(func):
    """Decorator for async Playwright functions with mite integration"""

    @wraps(func)
    async def wrapper(ctx, *args, **kwargs):
        playwright = await async_playwright().start()
        try:
            wrapped_playwright = PlaywrightWrapper(playwright, ctx)
            return await func(ctx, wrapped_playwright, *args, **kwargs)
        finally:
            await playwright.stop()

    return wrapper
