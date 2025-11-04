from contextlib import asynccontextmanager
from .tracing import get_tracer, is_tracing_enabled

# Expose a module-level placeholder so tests can patch Context
Context = None

def patch_context_transaction():
    """
    Patch the mite Context.transaction method to add spans
    """
    if not is_tracing_enabled():
        return
        
    try:
        # Prefer module-level placeholder if tests have patched it
        try:
            original_transaction = Context.transaction
            TargetContext = Context
        except Exception:
            from mite.context import Context as TargetContext
            original_transaction = TargetContext.transaction
        
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
                    if span:
                        span.record_exception(exc)
                        try:
                            from opentelemetry.trace import Status, StatusCode
                            span.set_status(Status(StatusCode.ERROR, str(exc)))
                        except ImportError:
                            pass
                    raise
        
        # Replace the method on whichever target was resolved
        try:
            TargetContext.transaction = traced_transaction
        except Exception:
            pass
        
    except ImportError:
        # Context class not found or different structure
        pass