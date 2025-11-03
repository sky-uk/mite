"""
Initialize OpenTelemetry tracer/meter conditionally. Safe no-op if opentelemetry is not installed.
"""
from typing import Optional
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
    from opentelemetry.trace import Status, StatusCode
    # Optional exporters imported lazily when configured
except ImportError:
    OTEL_AVAILABLE = False

_tracer = None
_meter = None

def init_tracing():
    """Initialize OpenTelemetry SDK with configuration from environment"""
    global _tracer, _meter
    
    if not OTEL_AVAILABLE:
        return
        
    cfg = get_otel_config()
    if not cfg["enabled"]:
        return
    # If a TracerProvider is already set (for example by tests), don't
    # override it. Respect externally configured provider.
    current_provider = trace.get_tracer_provider()
    try:
        from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
    except Exception:
        SDKTracerProvider = TracerProvider

    if isinstance(current_provider, SDKTracerProvider):
        # Use existing provider; set local tracer and meter references
        _tracer = trace.get_tracer(__name__)
        try:
            _meter = metrics.get_meter(__name__)
        except Exception:
            _meter = None
        return

    # Create resource with service name
    resource = Resource.create({"service.name": cfg["service_name"]})

    # Initialize tracing
    sampler = TraceIdRatioBased(cfg["sampler_ratio"])
    provider = TracerProvider(resource=resource, sampler=sampler)
    
    # Configure span processor and exporter
    span_proc = cfg["span_processor"]
    if span_proc == "console":
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    elif span_proc == "batch":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    elif span_proc == "zipkin" and cfg["otlp_endpoint"]:
        try:
            from opentelemetry.exporter.zipkin.json import ZipkinExporter
        except Exception:
            ZipkinExporter = None

        if ZipkinExporter:
            try:
                zipkin_exporter = ZipkinExporter(
                    endpoint=cfg["otlp_endpoint"],
                    timeout=cfg["export_timeout"],
                )
                provider.add_span_processor(BatchSpanProcessor(
                    zipkin_exporter,
                    max_export_batch_size=cfg["max_export_batch_size"]
                ))
            except Exception:
                breakpoint()
                # If exporter fails to initialize, fall back to console exporter
                provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        else:
            # Zipkin exporter not installed - fall back to console exporter
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    elif span_proc == "otlp" and cfg["otlp_endpoint"]:
        try:
            if cfg["otlp_protocol"] == "grpc":
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            else:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            
            # Parse headers if provided
            headers = {}
            if cfg["otlp_headers"]:
                for header in cfg["otlp_headers"].split(","):
                    if "=" in header:
                        key, value = header.split("=", 1)
                        headers[key.strip()] = value.strip()
            
            otlp_exporter = OTLPSpanExporter(
                endpoint=cfg["otlp_endpoint"],
                headers=headers,
                timeout=cfg["export_timeout"]
            )
            provider.add_span_processor(BatchSpanProcessor(
                otlp_exporter,
                max_export_batch_size=cfg["max_export_batch_size"]
            ))
        except ImportError:
            # OTLP exporter not available, fall back to console
            provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    
    # Set global tracer provider
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(__name__)
    
    # Initialize metrics (basic setup - console export not available)
    meter_provider = MeterProvider(resource=resource)
    metrics.set_meter_provider(meter_provider)
    _meter = metrics.get_meter(__name__)

def get_tracer():
    """Get the configured tracer or a no-op tracer if OTel unavailable"""
    global _tracer
    if _tracer:
        return _tracer

    cfg = get_otel_config()
    # If OpenTelemetry is not available or tracing is explicitly disabled,
    # return a no-op tracer that behaves the way tests expect (context manager
    # returns None).
    if not OTEL_AVAILABLE or not cfg.get("enabled", False):
        class _NoopTracer:
            def start_as_current_span(self, *args, **kwargs):
                class _NoopSpan:
                    def __enter__(self):
                        return None
                    def __exit__(self, exc_type, exc, tb):
                        return False
                    def end(self):
                        pass
                    def set_attribute(self, key, value):
                        pass
                    def record_exception(self, exception):
                        pass
                    def set_status(self, status):
                        pass
                return _NoopSpan()

            def start_span(self, name, **kwargs):
                class _NoopSpan:
                    def end(self):
                        pass
                    def set_attribute(self, key, value):
                        pass
                    def record_exception(self, exception):
                        pass
                    def set_status(self, status):
                        pass
                return _NoopSpan()

        return _NoopTracer()

    # If a tracer provider has been installed externally (e.g. tests), use it
    current_provider = trace.get_tracer_provider()
    try:
        from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
    except Exception:
        SDKTracerProvider = TracerProvider

    if isinstance(current_provider, SDKTracerProvider):
        _tracer = trace.get_tracer(__name__)
        return _tracer

    # Otherwise initialize a provider managed by mite
    init_tracing()
    return trace.get_tracer(__name__)

def get_meter():
    """Get the configured meter or a no-op meter if OTel unavailable"""
    global _meter
    if _meter:
        return _meter

    cfg = get_otel_config()
    if not OTEL_AVAILABLE or not cfg.get("enabled", False):
        # Return no-op meter
        class _NoopMeter:
            def create_counter(self, name, **kwargs):
                class _NoopCounter:
                    def add(self, amount, attributes=None):
                        pass
                return _NoopCounter()

            def create_histogram(self, name, **kwargs):
                class _NoopHistogram:
                    def record(self, amount, attributes=None):
                        pass
                return _NoopHistogram()

            def create_up_down_counter(self, name, **kwargs):
                class _NoopUpDownCounter:
                    def add(self, amount, attributes=None):
                        pass
                return _NoopUpDownCounter()

        return _NoopMeter()

    # If an external provider is present, use its meter
    current_provider = trace.get_tracer_provider()
    try:
        from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider
    except Exception:
        SDKTracerProvider = TracerProvider

    if isinstance(current_provider, SDKTracerProvider):
        try:
            return metrics.get_meter(__name__)
        except Exception:
            return _NoopMeter()

    # Otherwise initialize providers and return a real meter
    init_tracing()
    return metrics.get_meter(__name__)

def is_tracing_enabled():
    """Check if tracing is actually enabled and available"""
    print("TRACE AVAILABILITY:", OTEL_AVAILABLE and get_otel_config()["enabled"])
    return OTEL_AVAILABLE and get_otel_config()["enabled"]