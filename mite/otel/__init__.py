try:
    from .instrumentation import trace_journey, trace_transaction, mite_http_traced
    from .context import inject_headers
    from .config import is_tracing_enabled

    __all__ = ["trace_journey", "trace_transaction", "mite_http_traced", "inject_headers", "enable_tracing"]

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
        from .tracing import init_tracing
        from .context_integration import patch_context_transaction
        from .acurl_integration import patch_acurl_session

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

