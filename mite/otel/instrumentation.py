import functools
from contextlib import asynccontextmanager
from .tracing import get_tracer, handle_span_error


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
