import functools
import threading
from contextlib import asynccontextmanager
from contextvars import ContextVar

from .config import is_tracing_enabled
from .tracing import get_tracer, handle_span_error

# Context variable to track if we're inside a traced journey
_in_traced_journey: ContextVar[bool] = ContextVar('in_traced_journey', default=False)

# Lock for lazy patching to ensure it only happens once
_patching_lock = threading.Lock()


def _get_span_kind_internal():
    """Get SpanKind.INTERNAL if available"""
    try:
        from opentelemetry.trace import SpanKind

        return SpanKind.INTERNAL
    except ImportError:
        return None


def _start_span(tracer, name, span_kind):
    """Start a span with optional span kind"""
    if span_kind is not None:
        return tracer.start_as_current_span(name, kind=span_kind)
    return tracer.start_as_current_span(name)


def trace_journey(journey_name: str):
    """Decorator for journey functions to create root spans"""

    def decorator(journey_func):
        tracer = get_tracer()
        span_kind = _get_span_kind_internal()
        span_name = f"journey.{journey_name}"

        @functools.wraps(journey_func)
        async def async_wrapper(*args, **kwargs):
            with _start_span(tracer, span_name, span_kind) as span:
                if span:
                    span.set_attribute("mite.journey.name", journey_name)
                try:
                    return await journey_func(*args, **kwargs)
                except Exception as exc:
                    handle_span_error(span, exc)
                    raise

        return async_wrapper

    return decorator


@asynccontextmanager
async def trace_transaction(transaction_name: str, **attributes):
    """Context manager for transaction spans (nested under journey)"""
    tracer = get_tracer()
    span_kind = _get_span_kind_internal()
    span_name = f"transaction.{transaction_name}"

    with _start_span(tracer, span_name, span_kind) as span:
        if span:
            span.set_attribute("mite.transaction.name", transaction_name)
            for key, value in attributes.items():
                span.set_attribute(f"mite.transaction.{key}", str(value))
        try:
            yield span
        except Exception as exc:
            handle_span_error(span, exc)
            raise


def mite_http_traced(func):
    """
    Decorator for mite HTTP journeys with OpenTelemetry tracing.

    Combines @mite_http functionality with automatic journey span creation.
    Falls back to plain @mite_http behavior when tracing is disabled.

    Usage:
        from mite.otel import mite_http_traced

        @mite_http_traced
        async def my_journey(ctx):
            async with ctx.transaction("My Transaction"):
                await ctx.http.get("https://example.com")
    """
    # Import mite_http's SessionPool here to avoid import order issues
    from mite_http import SessionPool

    # If tracing is not enabled, just apply the standard mite_http decorator
    if not is_tracing_enabled():
        return SessionPool.decorator(func)

    # Trigger lazy patching on first use
    _ensure_patching_applied()

    # Apply the mite_http decorator first
    wrapped_func = SessionPool.decorator(func)

    @functools.wraps(func)
    async def tracing_wrapper(*args, **kwargs):
        tracer = get_tracer()
        journey_name = func.__name__
        span_kind = _get_span_kind_internal()
        span_name = f"journey.{journey_name}"

        # Set context variable to indicate we're in a traced journey
        token = _in_traced_journey.set(True)
        try:
            with _start_span(tracer, span_name, span_kind) as span:
                if span:
                    span.set_attribute("mite.journey.name", journey_name)
                    span.set_attribute("mite.journey.type", "http")

                    # Add any context info available
                    if args and hasattr(args[0], "__class__"):
                        span.set_attribute("mite.context.type", args[0].__class__.__name__)

                try:
                    return await wrapped_func(*args, **kwargs)
                except Exception as exc:
                    handle_span_error(span, exc)
                    raise
        finally:
            # Reset context variable
            _in_traced_journey.reset(token)

    return tracing_wrapper


def _ensure_patching_applied():
    """Ensure lazy patching has been applied (thread-safe, idempotent)"""
    from .acurl_integration import patch_acurl_session
    from .context_integration import patch_context_transaction

    with _patching_lock:
        # Patches check their own _patched flags internally
        patch_acurl_session()
        patch_context_transaction()


def is_in_traced_journey() -> bool:
    """Check if currently executing within a traced journey"""
    return _in_traced_journey.get(False)
