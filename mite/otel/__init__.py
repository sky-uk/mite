try:
    from .config import is_tracing_enabled
    from .instrumentation import mite_http_traced  # noqa: F401

    def enable_tracing():
        """
        Enable OpenTelemetry tracing with lazy patching.

        This function initializes the OpenTelemetry SDK. Patching of ctx.transaction()
        and HTTP methods happens lazily when the first @mite_http_traced journey is
        decorated, ensuring zero overhead for @mite_http journeys.

        Call this explicitly if you need more control over when tracing is enabled.
        Otherwise, tracing is automatically enabled when MITE_CONF_OTEL_ENABLED=true.

        Note: For HTTP journeys, use the @mite_http_traced decorator instead of @mite_http.
        Only @mite_http_traced journeys and their transactions/requests will be traced.
        """
        from .tracing import init_tracing

        init_tracing()

    # Auto-initialize if enabled via environment variable
    if is_tracing_enabled():
        enable_tracing()

except ImportError:
    # OpenTelemetry not available - provide no-op
    __all__ = []

    def enable_tracing():
        """No-op when OpenTelemetry is not installed"""
        pass
