from typing import Dict, Optional

try:
    from opentelemetry.propagate import inject, extract
    from opentelemetry import context as otel_context
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


def extract_context_from_headers(headers: Dict[str, str]):
    """Extract OpenTelemetry context from HTTP headers and set as current"""
    if not _is_enabled():
        return None
    
    extracted_context = extract(headers)
    if extracted_context:
        return otel_context.attach(extracted_context)
    return None


def detach_context(token):
    """Detach previously attached context"""
    if _is_enabled() and token:
        otel_context.detach(token)


def extract_context(headers: Dict[str, str]) -> Optional[object]:
    """Extract OpenTelemetry context from incoming HTTP headers"""
    if not _is_enabled():
        return None
    return extract(headers)