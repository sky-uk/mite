import os
from unittest.mock import Mock

import pytest

from mite.context import Context

pytestmark = pytest.mark.asyncio


def setup_module(module):
    # Ensure telemetry enabled for tests; use simple processor to flush immediately
    os.environ["MITE_CONF_OTEL_ENABLED"] = "1"
    os.environ["MITE_CONF_OTEL_SPAN_PROCESSOR"] = "simple"
    os.environ["MITE_CONF_OTEL_SAMPLER_RATIO"] = "1.0"


def teardown_module(module):
    # Clean up env to not impact other tests
    for k in [
        "MITE_CONF_OTEL_ENABLED",
        "MITE_CONF_OTEL_SPAN_PROCESSOR",
        "MITE_CONF_OTEL_SAMPLER_RATIO",
    ]:
        os.environ.pop(k, None)


async def test_transaction_creates_span(monkeypatch):
    # Patch telemetry to capture spans via an in-memory exporter substitute
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            InMemorySpanExporter,
            SimpleSpanProcessor,
        )
    except Exception:
        pytest.skip("opentelemetry not installed")

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    send_fn = Mock()
    ctx = Context(send_fn, {}, id_data={"test": "T1", "journey": "mod:journey"})

    async with ctx.transaction("span_name"):
        pass

    finished = exporter.get_finished_spans()
    # Expect exactly one span (the transaction span) or possibly more if root journey span leaked into context, so >=1
    assert any(s.name == "span_name" for s in finished)
    target = [s for s in finished if s.name == "span_name"][0]
    assert target.attributes["mite.test"] == "T1"
    assert target.attributes["mite.journey_spec"] == "mod:journey"


async def test_exception_marks_span_error(monkeypatch):
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            InMemorySpanExporter,
            SimpleSpanProcessor,
        )
        from opentelemetry.trace import StatusCode
    except Exception:
        pytest.skip("opentelemetry not installed")

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    send_fn = Mock()
    ctx = Context(send_fn, {}, id_data={"test": "T2", "journey": "mod:journey"})

    class Boom(Exception):
        pass

    with pytest.raises(Boom):
        async with ctx.transaction("will_fail"):
            raise Boom("fail")

    spans = exporter.get_finished_spans()
    err_span = [s for s in spans if s.name == "will_fail"][0]
    assert err_span.status.status_code == StatusCode.ERROR
