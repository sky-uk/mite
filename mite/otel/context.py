from typing import Dict

try:
    from opentelemetry import context as otel_context
    from opentelemetry.propagate import inject

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


def _is_enabled():
    """Check if OTel is available and enabled"""
    if not OTEL_AVAILABLE:
        return False
    from .config import get_otel_config

    return get_otel_config().get("enabled", False)


def inject_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Inject OpenTelemetry trace context into HTTP headers"""
    if not _is_enabled():
        return headers

    inject(headers, context=otel_context.get_current())
    return headers
