"""
Integration with acurl HTTP client via mite_http callback mechanism
"""

import asyncio
import logging
from urllib.parse import urlparse
from .tracing import get_tracer, is_tracing_enabled
from .context import inject_headers
from .stats_integration import record_http_request

logger = logging.getLogger(__name__)

# Module-level placeholder so tests can patch
AcurlSessionWrapper = None


def _get_span_kind():
    """Get SpanKind.CLIENT if available, otherwise None"""
    try:
        from opentelemetry.trace import SpanKind

        return SpanKind.CLIENT
    except ImportError:
        return None


def _set_request_attributes(span, method, url):
    """Set all request-related span attributes"""
    if not span:
        return

    span.set_attribute("http.method", method)
    span.set_attribute("http.url", url)

    # Parse URL for additional attributes
    try:
        parsed = urlparse(url)
        if parsed.hostname:
            span.set_attribute("http.host", parsed.hostname)
        if parsed.scheme:
            span.set_attribute("http.scheme", parsed.scheme)
        if parsed.path:
            span.set_attribute("http.target", parsed.path)
    except Exception:
        pass


def _set_response_attributes(span, response, method_upper, url):
    """Set all response-related span attributes"""
    if not span or not response:
        return

    logger.debug(
        f"mite_http: completing span for {method_upper} {url}, status={getattr(response, 'status_code', 'unknown')}"
    )

    # Status code
    if hasattr(response, "status_code"):
        span.set_attribute("http.status_code", response.status_code)
        span.set_attribute("http.response.status_code", response.status_code)

    # Timing metrics
    timing_attrs = [
        ("total_time", "http.response.time.total"),
        ("starttransfer_time", "http.response.time.first_byte"),
        ("namelookup_time", "http.response.time.dns"),
        ("connect_time", "http.response.time.connect"),
    ]
    for attr_name, span_attr in timing_attrs:
        if hasattr(response, attr_name):
            span.set_attribute(span_attr, getattr(response, attr_name))

    # Response size
    if hasattr(response, "download_size"):
        span.set_attribute("http.response.body.size", response.download_size)

    # Content-Length header
    if hasattr(response, "headers"):
        content_length = response.headers.get("content-length")
        if content_length:
            span.set_attribute("http.response.header.content-length", content_length)


def _prepare_headers(kwargs):
    """Prepare headers dict with injected tracing context"""
    headers = kwargs.get("headers", {})
    if not isinstance(headers, dict):
        headers = dict(headers) if headers else {}
    inject_headers(headers)
    kwargs["headers"] = headers
    return kwargs


def _record_error_metrics(span, exc, method_upper, start_time):
    """Record exception in span and metrics"""
    if span:
        span.record_exception(exc)
        try:
            from opentelemetry.trace import Status, StatusCode

            span.set_status(Status(StatusCode.ERROR, str(exc)))
        except ImportError:
            pass

    duration = asyncio.get_event_loop().time() - start_time
    record_http_request(method_upper, 0, duration, error=True)


def _record_success_metrics(response, start_time):
    """Record metrics for successful requests"""
    duration = asyncio.get_event_loop().time() - start_time
    method = (
        getattr(response.request, "method", "unknown")
        if hasattr(response, "request")
        else "unknown"
    )
    if isinstance(method, bytes):
        method = method.decode()
    record_http_request(method, response.status_code, duration)


def _create_http_method_wrapper(method_name):
    """Create a wrapper for HTTP methods that creates spans"""

    async def traced_method(self, url, **kwargs):
        """Wrapper that creates HTTP client spans with proper semantic conventions"""
        tracer = get_tracer()
        method_upper = method_name.upper()
        span_name = f"HTTP {method_upper}"
        start_time = asyncio.get_event_loop().time()

        # Create span context manager
        span_kind = _get_span_kind()
        if span_kind is not None:
            cm = tracer.start_as_current_span(span_name, kind=span_kind)
        else:
            cm = tracer.start_as_current_span(span_name)

        # Enter span context (handle noop tracer)
        span = None
        span_cm = None
        try:
            span = cm.__enter__()
            span_cm = cm
        except Exception:
            # No context manager provided by noop tracer
            pass

        # Set request attributes
        _set_request_attributes(span, method_upper, url)

        # Inject distributed tracing headers
        kwargs = _prepare_headers(kwargs)

        # Execute request with error handling
        response = None
        exc_info = (None, None, None)
        try:
            # Get the original method from the wrapped session
            original_method = getattr(self._AcurlSessionWrapper__session, method_name)
            response = await original_method(url, **kwargs)
            return response

        except Exception as exc:
            _record_error_metrics(span, exc, method_upper, start_time)
            import sys

            exc_info = sys.exc_info()
            raise

        finally:
            # Set response attributes and record metrics
            if response:
                _set_response_attributes(span, response, method_upper, url)
                _record_success_metrics(response, start_time)

            # Exit span context manager
            if span_cm:
                try:
                    span_cm.__exit__(*exc_info)
                except Exception:
                    logger.debug("Error exiting span context manager", exc_info=True)

    return traced_method


def patch_acurl_session():
    """
    Patch mite_http's AcurlSessionWrapper to add HTTP client spans
    """
    if not is_tracing_enabled():
        logger.debug("mite_http: tracing not enabled, skipping patch")
        return

    try:
        # Import from mite_http instead of acurl directly
        try:
            from mite_http import AcurlSessionWrapper as _AcurlSessionWrapper
        except ImportError:
            logger.debug("Could not import AcurlSessionWrapper from mite_http")
            return

        # Expose for tests / external inspection
        global AcurlSessionWrapper
        AcurlSessionWrapper = _AcurlSessionWrapper

        logger.debug("mite_http: AcurlSessionWrapper imported, patching HTTP methods")

        # Patch the HTTP methods to create spans
        http_methods = ["get", "post", "put", "patch", "delete", "head", "options"]

        for method_name in http_methods:
            wrapped_method = _create_http_method_wrapper(method_name)
            setattr(AcurlSessionWrapper, method_name, wrapped_method)
            logger.debug(f"mite_http: patched {method_name} method")

        logger.debug("Successfully patched mite_http AcurlSessionWrapper for tracing")

    except (ImportError, AttributeError) as exc:
        logger.debug(f"Could not patch mite_http: {exc}", exc_info=True)
