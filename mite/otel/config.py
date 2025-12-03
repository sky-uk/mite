import os
from typing import Any, Dict


def get_otel_config() -> Dict[str, Any]:
    """Get OpenTelemetry configuration from environment variables"""
    return {
        "enabled": os.getenv("MITE_CONF_OTEL_ENABLED", "false").lower()
        in ("1", "true", "yes"),
        "service_name": os.getenv("MITE_CONF_OTEL_SERVICE_NAME", "mite"),
        "sampler_ratio": float(os.getenv("MITE_CONF_OTEL_SAMPLER_RATIO", "1.0")),
        "span_processor": os.getenv("MITE_CONF_OTEL_SPAN_PROCESSOR", "console").lower(),
        "otlp_endpoint": os.getenv("MITE_CONF_OTEL_OTLP_ENDPOINT", ""),
        "otlp_protocol": os.getenv("MITE_CONF_OTEL_OTLP_PROTOCOL", "http/protobuf"),
        "otlp_headers": os.getenv("MITE_CONF_OTEL_OTLP_HEADERS", ""),
        "max_export_batch_size": int(
            os.getenv("MITE_CONF_OTEL_MAX_EXPORT_BATCH_SIZE", "512")
        ),
        "export_timeout": int(os.getenv("MITE_CONF_OTEL_EXPORT_TIMEOUT", "30")),
    }


def is_tracing_enabled() -> bool:
    """Quick check if tracing is enabled"""
    return get_otel_config()["enabled"]
