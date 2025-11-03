"""
Manual instrumentation API for advanced usage
"""
import asyncio
import functools
from contextlib import asynccontextmanager
from .tracing import get_tracer

def _get_span_kind_internal():
    """Get SpanKind.INTERNAL if available"""
    try:
        from opentelemetry.trace import SpanKind
        return SpanKind.INTERNAL
    except ImportError:
        return None

def trace_journey(journey_name: str):
    """Decorator for journey functions to create root spans"""
    def decorator(journey_func):
        if asyncio.iscoroutinefunction(journey_func):
            @functools.wraps(journey_func)
            async def async_wrapper(*args, **kwargs):
                tracer = get_tracer()
                span_kind = _get_span_kind_internal()
                # Use context manager so the SDK captures the active span
                if span_kind is not None:
                    ctx = tracer.start_as_current_span(f"journey.{journey_name}", kind=span_kind)
                else:
                    ctx = tracer.start_as_current_span(f"journey.{journey_name}")
                    
                with ctx as span:
                    if span:
                        span.set_attribute("mite.journey.name", journey_name)
                    try:
                        return await journey_func(*args, **kwargs)
                    except Exception as exc:
                        if span:
                            span.record_exception(exc)
                            try:
                                from opentelemetry.trace import Status, StatusCode
                                span.set_status(Status(StatusCode.ERROR))
                            except ImportError:
                                pass
                        raise
            return async_wrapper
        else:
            @functools.wraps(journey_func)
            def sync_wrapper(*args, **kwargs):
                tracer = get_tracer()
                span_kind = _get_span_kind_internal()
                if span_kind is not None:
                    ctx = tracer.start_as_current_span(f"journey.{journey_name}", kind=span_kind)
                else:
                    ctx = tracer.start_as_current_span(f"journey.{journey_name}")
                    
                with ctx as span:
                    if span:
                        span.set_attribute("mite.journey.name", journey_name)
                    try:
                        return journey_func(*args, **kwargs)
                    except Exception as exc:
                        if span:
                            span.record_exception(exc)
                            try:
                                from opentelemetry.trace import Status, StatusCode
                                span.set_status(Status(StatusCode.ERROR))
                            except ImportError:
                                pass
                        raise
            return sync_wrapper
    return decorator

@asynccontextmanager
async def trace_transaction(transaction_name: str, **attributes):
    """Context manager for transaction spans (nested under journey)"""
    tracer = get_tracer()
    span_kind = _get_span_kind_internal()
    
    if span_kind is not None:
        ctx = tracer.start_as_current_span(f"transaction.{transaction_name}", kind=span_kind)
    else:
        ctx = tracer.start_as_current_span(f"transaction.{transaction_name}")
        
    with ctx as span:
        if span:
            span.set_attribute("mite.transaction.name", transaction_name)
            for key, value in attributes.items():
                span.set_attribute(f"mite.transaction.{key}", str(value))
        try:
            yield span
        except Exception as exc:
            if span:
                span.record_exception(exc)
                try:
                    from opentelemetry.trace import Status, StatusCode
                    span.set_status(Status(StatusCode.ERROR))
                except ImportError:
                    pass
            raise