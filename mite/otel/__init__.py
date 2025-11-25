from mite.otel.config import is_tracing_enabled
from mite.otel.instrumentation import mite_http_traced  # noqa: F401

# Auto-initialize if enabled via environment variable
if is_tracing_enabled():
    from mite.otel.tracing import init_tracing
    init_tracing()
