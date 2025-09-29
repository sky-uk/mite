import logging
import os
from typing import Optional

_logger = logging.getLogger(__name__)

_OTEL_ENABLED_ENV = "MITE_CONF_OTEL_ENABLED"
_OTEL_SAMPLER_RATIO_ENV = "MITE_CONF_OTEL_SAMPLER_RATIO"
_OTEL_SPAN_PROCESSOR_ENV = "MITE_CONF_OTEL_SPAN_PROCESSOR"  # batch|simple
_OTEL_SERVICE_NAME_ENV = "MITE_CONF_OTEL_SERVICE_NAME"
_OTEL_DEBUG_STACKTRACE_ENV = "MITE_CONF_OTEL_DEBUG_STACKTRACE"

_tracer_provider = None
_meter_provider = None
_span_exporter = None
_initialized = False
_debug_stacktrace = False


def is_enabled() -> bool:
    return os.environ.get(_OTEL_ENABLED_ENV, "0").lower() in ("1", "true", "yes")


def _load_otel():  # Lazy import helper
    from opentelemetry import metrics, trace  # type: ignore
    from opentelemetry.sdk.metrics import MeterProvider  # type: ignore
    from opentelemetry.sdk.resources import Resource  # type: ignore
    from opentelemetry.sdk.trace import TracerProvider  # type: ignore
    from opentelemetry.sdk.trace.export import (  # type: ignore
        BatchSpanProcessor,
        ConsoleSpanExporter,
        SimpleSpanProcessor,
    )

    return {
        "trace": trace,
        "metrics": metrics,
        "TracerProvider": TracerProvider,
        "SimpleSpanProcessor": SimpleSpanProcessor,
        "BatchSpanProcessor": BatchSpanProcessor,
        "ConsoleSpanExporter": ConsoleSpanExporter,
        "Resource": Resource,
        "MeterProvider": MeterProvider,
    }


def init(service_name: Optional[str] = None):
    global _initialized, _tracer_provider, _meter_provider, _span_exporter, _debug_stacktrace
    if _initialized:
        return
    if not is_enabled():
        _logger.info("OpenTelemetry disabled")
        _initialized = True
        return
    try:
        otel = _load_otel()
    except Exception as e:  # pragma: no cover - dependency absent
        _logger.warning("OpenTelemetry not available: %s", e)
        _initialized = True
        return

    from opentelemetry.sdk.trace.sampling import (  # type: ignore
        ParentBased,
        TraceIdRatioBased,
    )

    ratio = 0.01
    try:
        ratio = float(os.environ.get(_OTEL_SAMPLER_RATIO_ENV, ratio))
    except ValueError:
        _logger.warning("Invalid sampler ratio env, using default %s", ratio)

    sampler = ParentBased(TraceIdRatioBased(ratio))

    service_name = service_name or os.environ.get(_OTEL_SERVICE_NAME_ENV) or "mite"
    resource = otel["Resource"].create({"service.name": service_name})

    _tracer_provider = otel["TracerProvider"](sampler=sampler, resource=resource)

    processor_type = os.environ.get(_OTEL_SPAN_PROCESSOR_ENV, "batch").lower()
    span_exporter = otel["ConsoleSpanExporter"]()
    if processor_type == "simple":
        _tracer_provider.add_span_processor(otel["SimpleSpanProcessor"](span_exporter))
    else:
        _tracer_provider.add_span_processor(otel["BatchSpanProcessor"](span_exporter))

    otel["trace"].set_tracer_provider(_tracer_provider)

    _meter_provider = otel["MeterProvider"]()
    otel["metrics"].set_meter_provider(_meter_provider)

    _debug_stacktrace = os.environ.get(_OTEL_DEBUG_STACKTRACE_ENV, "0").lower() in (
        "1",
        "true",
        "yes",
    )

    _initialized = True
    _logger.info(
        "Initialized OpenTelemetry (ratio=%s, processor=%s, service_name=%s)",
        ratio,
        processor_type,
        service_name,
    )


def get_tracer():
    from opentelemetry import trace  # type: ignore

    if not _initialized:
        init()
    return trace.get_tracer("mite")


def record_exception(span, exc):  # helper used by instrumentation
    if not is_enabled():
        return
    try:
        from opentelemetry.trace import Status, StatusCode  # type: ignore

        span.record_exception(exc)
        span.set_status(Status(StatusCode.ERROR))
    except Exception:  # pragma: no cover
        _logger.exception("Failed to record exception on span")


def debug_stacktrace_enabled():
    return _debug_stacktrace


def shutdown():
    global _tracer_provider
    if _tracer_provider is None:
        return
    try:
        _tracer_provider.shutdown()  # flushes span processors
    except Exception:  # pragma: no cover
        _logger.exception("Error during tracer provider shutdown")
