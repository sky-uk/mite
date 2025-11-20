from .config import get_otel_config

OTEL_AVAILABLE = True
try:
    from opentelemetry import metrics, trace
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SimpleSpanProcessor,
    )
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
except ImportError:
    OTEL_AVAILABLE = False


class _TracingState:
    """Holds tracing state"""

    def __init__(self):
        self.tracer = None
        self.meter = None


_state = _TracingState()


def handle_span_error(span, exc):
    """Record exception and set error status on span"""
    if not span:
        return

    span.record_exception(exc)
    try:
        from opentelemetry.trace import Status, StatusCode

        span.set_status(Status(StatusCode.ERROR))
    except ImportError:
        pass


def _is_sdk_provider_configured():
    """Check if an SDK TracerProvider is already configured"""
    if not OTEL_AVAILABLE:
        return False
    try:
        from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider

        return isinstance(trace.get_tracer_provider(), SDKTracerProvider)
    except Exception:
        return False


def _configure_exporter(provider, cfg):
    """Configure span exporter based on config"""
    proc = cfg["span_processor"]
    endpoint = cfg["otlp_endpoint"]

    # Console exporters (simple or batched)
    if proc in ("console", "batch"):
        exporter = ConsoleSpanExporter()
        processor = BatchSpanProcessor if proc == "batch" else SimpleSpanProcessor
        provider.add_span_processor(processor(exporter))
        return

    # Zipkin exporter
    if proc == "zipkin" and endpoint:
        try:
            from opentelemetry.exporter.zipkin.json import ZipkinExporter

            exporter = ZipkinExporter(endpoint=endpoint, timeout=cfg["export_timeout"])
            provider.add_span_processor(
                BatchSpanProcessor(
                    exporter, max_export_batch_size=cfg["max_export_batch_size"]
                )
            )
            return
        except ImportError:
            pass  # Fall through to console fallback

    # OTLP exporter
    if proc == "otlp" and endpoint:
        try:
            if cfg["otlp_protocol"] == "grpc":
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )
            else:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                    OTLPSpanExporter,
                )

            headers = {}
            if cfg["otlp_headers"]:
                for h in cfg["otlp_headers"].split(","):
                    if "=" in h:
                        k, v = h.split("=", 1)
                        headers[k.strip()] = v.strip()

            exporter = OTLPSpanExporter(
                endpoint=endpoint, headers=headers, timeout=cfg["export_timeout"]
            )
            provider.add_span_processor(
                BatchSpanProcessor(
                    exporter, max_export_batch_size=cfg["max_export_batch_size"]
                )
            )
            return
        except ImportError:
            pass  # Fall through to console fallback

    # Fallback to console for any other case (no endpoint, unknown processor, import failure)
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))


def init_tracing():
    """Initialize OpenTelemetry SDK with configuration from environment"""
    if not OTEL_AVAILABLE:
        return

    cfg = get_otel_config()
    if not cfg["enabled"]:
        return

    # Create provider with resource and sampler
    resource = Resource.create({"service.name": cfg["service_name"]})
    sampler = TraceIdRatioBased(cfg["sampler_ratio"])
    provider = TracerProvider(resource=resource, sampler=sampler)

    # Configure exporter
    _configure_exporter(provider, cfg)

    trace.set_tracer_provider(provider)
    _state.tracer = trace.get_tracer(__name__)

    meter_provider = MeterProvider(resource=resource)
    metrics.set_meter_provider(meter_provider)
    _state.meter = metrics.get_meter(__name__)


def get_tracer():
    """Get the configured tracer"""
    if _state.tracer:
        return _state.tracer

    if not OTEL_AVAILABLE:
        raise RuntimeError(
            "OpenTelemetry is not installed. Install with: pip install mite[otel]"
        )

    cfg = get_otel_config()
    if not cfg.get("enabled", False):
        raise RuntimeError(
            "OpenTelemetry is disabled. Set MITE_CONF_OTEL_ENABLED=true to enable tracing"
        )

    if _is_sdk_provider_configured():
        _state.tracer = trace.get_tracer(__name__)
        return _state.tracer

    init_tracing()
    return trace.get_tracer(__name__)


def get_meter():
    """Get the configured meter"""
    if _state.meter:
        return _state.meter

    if not OTEL_AVAILABLE:
        raise RuntimeError(
            "OpenTelemetry is not installed. Install with: pip install mite[otel]"
        )

    cfg = get_otel_config()
    if not cfg.get("enabled", False):
        raise RuntimeError(
            "OpenTelemetry is disabled. Set MITE_CONF_OTEL_ENABLED=true to enable tracing"
        )

    if _is_sdk_provider_configured():
        _state.meter = metrics.get_meter(__name__)
        return _state.meter

    init_tracing()
    return metrics.get_meter(__name__)
