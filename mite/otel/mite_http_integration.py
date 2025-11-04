import functools
from .tracing import get_tracer
from .config import is_tracing_enabled


def patch_mite_http_decorator():
    """
    Enhance the @mite_http decorator to create journey spans automatically
    """
    if not is_tracing_enabled():
        return

    try:
        import mite_http
        from mite_http import mite_http as original_decorator

        def tracing_mite_http(func):
            """Enhanced mite_http decorator with automatic tracing"""
            # Apply original decorator first
            wrapped_func = original_decorator(func)

            @functools.wraps(func)
            async def tracing_wrapper(*args, **kwargs):
                tracer = get_tracer()
                journey_name = func.__name__

                with tracer.start_as_current_span(f"journey.{journey_name}") as span:
                    if span:
                        span.set_attribute("mite.journey.name", journey_name)
                        span.set_attribute("mite.journey.type", "http")

                        # Add any context info available
                        if args and hasattr(args[0], "__class__"):
                            span.set_attribute(
                                "mite.context.type", args[0].__class__.__name__
                            )

                    try:
                        return await wrapped_func(*args, **kwargs)
                    except Exception as exc:
                        if span:
                            span.record_exception(exc)
                            try:
                                from opentelemetry.trace import Status, StatusCode

                                span.set_status(Status(StatusCode.ERROR, str(exc)))
                            except ImportError:
                                pass
                        raise

            return tracing_wrapper

        # Replace the decorator
        mite_http.mite_http = tracing_mite_http

    except ImportError:
        pass  # mite_http not available
