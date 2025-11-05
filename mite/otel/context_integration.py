from contextlib import asynccontextmanager
from .tracing import get_tracer, handle_span_error
from .config import is_tracing_enabled


def patch_context_transaction():
    """
    Patch the mite Context.transaction method to add spans
    """
    if not is_tracing_enabled():
        return

    try:
        from mite.context import Context

        original_transaction = Context.transaction

        @asynccontextmanager
        async def traced_transaction(self, name: str, **kwargs):
            """Enhanced transaction with automatic span creation"""
            tracer = get_tracer()

            with tracer.start_as_current_span(f"transaction.{name}") as span:
                if span:
                    span.set_attribute("mite.transaction.name", name)

                    # Add any additional attributes from kwargs
                    for key, value in kwargs.items():
                        if isinstance(value, (str, int, float, bool)):
                            span.set_attribute(f"mite.transaction.{key}", value)
                        else:
                            span.set_attribute(f"mite.transaction.{key}", str(value))

                try:
                    # Use original transaction context manager
                    async with original_transaction(self, name, **kwargs) as tx:
                        yield tx
                except Exception as exc:
                    handle_span_error(span, exc)
                    raise

        # Replace the method
        Context.transaction = traced_transaction

    except ImportError:
        pass  # Context class not found
