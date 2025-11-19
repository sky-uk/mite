try:
    from .config import is_tracing_enabled
    from .instrumentation import mite_http_traced  # noqa: F401

    def enable_tracing():
        """
        Enable OpenTelemetry tracing with automatic patching.

        This function initializes the OpenTelemetry SDK and applies patches to:
        - ctx.transaction() method (transaction spans)
        - acurl Session (HTTP request spans)

        Call this explicitly if you need more control over when tracing is enabled.
        Otherwise, tracing is automatically enabled when MITE_CONF_OTEL_ENABLED=true.

        Note: For HTTP journeys, use the @mite_http_traced decorator instead of @mite_http.
        """
        from .acurl_integration import patch_acurl_session
        from .context_integration import patch_context_transaction
        from .tracing import init_tracing

        init_tracing()
        patch_context_transaction()
        patch_acurl_session()

    # Auto-initialize if enabled via environment variable
    if is_tracing_enabled():
        enable_tracing()

except ImportError:
    # OpenTelemetry not available - provide no-op
    __all__ = []

    def enable_tracing():
        """No-op when OpenTelemetry is not installed"""
        pass
