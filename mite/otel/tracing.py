"""
Initialize OpenTelemetry tracer/meter conditionally. Safe no-op if opentelemetry is not installed.
"""
from .config import get_otel_config

OTEL_AVAILABLE = True
try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import (
        ConsoleSpanExporter,
        SimpleSpanProcessor,
        BatchSpanProcessor,
    )
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
except ImportError:
    OTEL_AVAILABLE = False

_tracer = None
_meter = None
_noop_tracer = None
_noop_meter = None


def _get_noop_tracer():
    """Get or create a singleton no-op tracer"""
    global _noop_tracer
    if _noop_tracer:
        return _noop_tracer
    
    class NoopSpan:
        def __enter__(self): return None
        def __exit__(self, *args): return False
        def end(self): pass
        def set_attribute(self, k, v): pass
        def record_exception(self, e): pass
        def set_status(self, s): pass
    
    class NoopTracer:
        def start_as_current_span(self, *args, **kwargs): return NoopSpan()
        def start_span(self, name, **kwargs): return NoopSpan()
    
    _noop_tracer = NoopTracer()
    return _noop_tracer


def _get_noop_meter():
    """Get or create a singleton no-op meter"""
    global _noop_meter
    if _noop_meter:
        return _noop_meter
    
    class NoopMetric:
        def add(self, amount, attributes=None): pass
        def record(self, amount, attributes=None): pass
    
    class NoopMeter:
        def create_counter(self, name, **kwargs): return NoopMetric()
        def create_histogram(self, name, **kwargs): return NoopMetric()
        def create_up_down_counter(self, name, **kwargs): return NoopMetric()
    
    _noop_meter = NoopMeter()
    return _noop_meter


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
    
    # Console exporters
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
            provider.add_span_processor(BatchSpanProcessor(
                exporter, max_export_batch_size=cfg["max_export_batch_size"]))
            return
        except Exception:
            pass  # Fall through to console
    
    # OTLP exporter
    if proc == "otlp" and endpoint:
        try:
            if cfg["otlp_protocol"] == "grpc":
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            else:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            
            headers = {}
            if cfg["otlp_headers"]:
                for h in cfg["otlp_headers"].split(","):
                    if "=" in h:
                        k, v = h.split("=", 1)
                        headers[k.strip()] = v.strip()
            
            exporter = OTLPSpanExporter(
                endpoint=endpoint, headers=headers, timeout=cfg["export_timeout"])
            provider.add_span_processor(BatchSpanProcessor(
                exporter, max_export_batch_size=cfg["max_export_batch_size"]))
            return
        except ImportError:
            pass  # Fall through to console
    
    # Default fallback to console
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))



def init_tracing():
    """Initialize OpenTelemetry SDK with configuration from environment"""
    global _tracer, _meter
    
    if not OTEL_AVAILABLE:
        return
    
    cfg = get_otel_config()
    if not cfg["enabled"]:
        return
    
    # If a TracerProvider is already set (e.g., by tests), respect it
    if _is_sdk_provider_configured():
        _tracer = trace.get_tracer(__name__)
        try:
            _meter = metrics.get_meter(__name__)
        except Exception:
            _meter = None
        return

    # Create provider with resource and sampler
    resource = Resource.create({"service.name": cfg["service_name"]})
    sampler = TraceIdRatioBased(cfg["sampler_ratio"])
    provider = TracerProvider(resource=resource, sampler=sampler)
    
    # Configure exporter
    _configure_exporter(provider, cfg)
    
    # Set global providers
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(__name__)
    
    meter_provider = MeterProvider(resource=resource)
    metrics.set_meter_provider(meter_provider)
    _meter = metrics.get_meter(__name__)


def get_tracer():
    """Get the configured tracer or a no-op tracer if OTel unavailable"""
    global _tracer
    
    if _tracer:
        return _tracer

    cfg = get_otel_config()
    if not OTEL_AVAILABLE or not cfg.get("enabled", False):
        return _get_noop_tracer()

    if _is_sdk_provider_configured():
        _tracer = trace.get_tracer(__name__)
        return _tracer

    init_tracing()
    return trace.get_tracer(__name__)


def get_meter():
    """Get the configured meter or a no-op meter if OTel unavailable"""
    global _meter
    
    if _meter:
        return _meter

    cfg = get_otel_config()
    if not OTEL_AVAILABLE or not cfg.get("enabled", False):
        return _get_noop_meter()

    if _is_sdk_provider_configured():
        try:
            _meter = metrics.get_meter(__name__)
            return _meter
        except Exception:
            return _get_noop_meter()

    init_tracing()
    return metrics.get_meter(__name__)


def is_tracing_enabled():
    """Check if tracing is actually enabled and available"""
    return OTEL_AVAILABLE and get_otel_config()["enabled"]