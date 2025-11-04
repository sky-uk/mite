from urllib.parse import urlparse
from .tracing import get_tracer
from .config import is_tracing_enabled
from .context import inject_headers

# Import OpenTelemetry types at module level with fallbacks
try:
    from opentelemetry.trace import SpanKind, Status, StatusCode

    SPAN_KIND_CLIENT = SpanKind.CLIENT
    STATUS_AVAILABLE = True
except ImportError:
    SPAN_KIND_CLIENT = None
    STATUS_AVAILABLE = False


def _get_span_kind():
    """Get SpanKind.CLIENT if available, otherwise None"""
    return SPAN_KIND_CLIENT


def _set_span_attributes(span, method, url, response=None):
    """Set request and optionally response attributes on span"""
    if not span:
        return

    # Request attributes
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

    # Response attributes (if provided)
    if response:
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
                span.set_attribute(
                    "http.response.header.content-length", content_length
                )


def _prepare_headers(kwargs):
    """Prepare headers dict with injected tracing context"""
    headers = kwargs.get("headers", {})
    if not isinstance(headers, dict):
        headers = dict(headers) if headers else {}
    inject_headers(headers)
    kwargs["headers"] = headers
    return kwargs


def _record_error_metrics(span, exc):
    """Record exception in span"""
    if span:
        span.record_exception(exc)
        if STATUS_AVAILABLE:
            span.set_status(Status(StatusCode.ERROR, str(exc)))


def _create_http_method_wrapper(method_name):
    """Create a wrapper for HTTP methods that creates spans"""

    async def traced_method(self, url, **kwargs):
        """Wrapper that creates HTTP client spans with proper semantic conventions"""
        tracer = get_tracer()
        method_upper = method_name.upper()
        span_name = f"HTTP {method_upper}"

        span_kind = _get_span_kind()
        if span_kind is not None:
            span_ctx = tracer.start_as_current_span(span_name, kind=span_kind)
        else:
            span_ctx = tracer.start_as_current_span(span_name)

        with span_ctx as span:
            # Set request attributes
            _set_span_attributes(span, method_upper, url)

            # Inject distributed tracing headers
            kwargs = _prepare_headers(kwargs)

            # Execute request with error handling
            try:
                # Get the original method from the wrapped session
                original_method = getattr(
                    self._AcurlSessionWrapper__session, method_name
                )
                response = await original_method(url, **kwargs)

                # Set response attributes
                _set_span_attributes(span, method_upper, url, response)

                return response

            except Exception as exc:
                _record_error_metrics(span, exc)
                raise

    return traced_method


def patch_acurl_session():
    """
    Patch mite_http's AcurlSessionWrapper to add HTTP client spans
    """
    if not is_tracing_enabled():
        return

    try:
        from mite_http import AcurlSessionWrapper

        # Patch the HTTP methods to create spans
        http_methods = ["get", "post", "put", "patch", "delete", "head", "options"]

        for method_name in http_methods:
            wrapped_method = _create_http_method_wrapper(method_name)
            setattr(AcurlSessionWrapper, method_name, wrapped_method)

    except (ImportError, AttributeError):
        pass  # Silently skip if patching fails
