"""
Context propagation for distributed tracing
"""
from typing import Dict, Optional

try:
    from opentelemetry.propagate import inject, extract
    from opentelemetry import context as otel_context
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

def inject_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Inject OpenTelemetry trace context into HTTP headers
    """
    # If OTel not installed or explicitly disabled, do nothing
    from .config import get_otel_config
    cfg = get_otel_config()
    if not OTEL_AVAILABLE or not cfg.get("enabled", False):
        return headers

    # Get current context and inject into headers
    current_context = otel_context.get_current()
    inject(headers, context=current_context)
    return headers

def extract_context_from_headers(headers: Dict[str, str]):
    """
    Extract OpenTelemetry context from HTTP headers and set as current
    """
    from .config import get_otel_config
    cfg = get_otel_config()
    if not OTEL_AVAILABLE or not cfg.get("enabled", False):
        return None

    # Extract context from headers
    extracted_context = extract(headers)
    if extracted_context:
        # Set as current context for this execution
        token = otel_context.attach(extracted_context)
        return token
    return None

def detach_context(token):
    """
    Detach previously attached context
    """
    from .config import get_otel_config
    cfg = get_otel_config()
    if OTEL_AVAILABLE and cfg.get("enabled", False) and token:
        otel_context.detach(token)

def extract_context(headers: Dict[str, str]) -> Optional[object]:
    """
    Extract OpenTelemetry context from incoming HTTP headers
    For compatibility with the public API
    """
    from .config import get_otel_config
    cfg = get_otel_config()
    if not OTEL_AVAILABLE or not cfg.get("enabled", False):
        return None

    return extract(headers)