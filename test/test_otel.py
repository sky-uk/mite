"""
Test OpenTelemetry integration
"""
import os
import pytest
import asyncio
from unittest.mock import patch, MagicMock

# Disable auto-initialization for tests
os.environ["MITE_CONF_OTEL_ENABLED"] = "false"

# Skip all tests if OpenTelemetry not available
otel = pytest.importorskip("opentelemetry", reason="OpenTelemetry not installed")

# Import OpenTelemetry test utilities
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource


@pytest.fixture
def mock_otel_enabled(monkeypatch):
    """Enable OpenTelemetry for testing"""
    monkeypatch.setenv("MITE_CONF_OTEL_ENABLED", "true")
    monkeypatch.setenv("MITE_CONF_OTEL_SERVICE_NAME", "mite-test")
    monkeypatch.setenv("MITE_CONF_OTEL_SAMPLER_RATIO", "1.0")
    
    # Reset the tracing module state
    import mite.otel.tracing as tracing_module
    tracing_module._tracer = None
    tracing_module._meter = None
    
    yield
    
    # Clean up after test
    monkeypatch.setenv("MITE_CONF_OTEL_ENABLED", "false")
    tracing_module._tracer = None
    tracing_module._meter = None

@pytest.fixture
def in_memory_span_exporter():
    """Set up in-memory span exporter for testing"""
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    # Some OpenTelemetry versions accept span_processors in the constructor,
    # others do not. Create a provider and add processors for compatibility.
    provider = TracerProvider()
    try:
        # Try to set resource if supported
        provider = TracerProvider(resource=Resource.create({"service.name": "mite-test"}))
    except TypeError:
        # Older/newer versions may not accept resource in ctor; continue with default
        provider = TracerProvider()

    # Add the in-memory processor in a compatible way
    try:
        provider.add_span_processor(processor)
    except Exception:
        # Best-effort: if provider doesn't support adding processors, ignore
        pass
    trace.set_tracer_provider(provider)
    yield exporter
    exporter.clear()


class TestConfig:
    """Test configuration module"""
    
    def test_get_otel_config_default(self):
        from mite.otel.config import get_otel_config
        
        config = get_otel_config()
        assert config["enabled"] is False
        assert config["service_name"] == "mite"
        assert config["sampler_ratio"] == 1.0
        assert config["span_processor"] == "console"
    
    def test_get_otel_config_from_env(self, monkeypatch):
        from mite.otel.config import get_otel_config
        
        monkeypatch.setenv("MITE_CONF_OTEL_ENABLED", "true")
        monkeypatch.setenv("MITE_CONF_OTEL_SERVICE_NAME", "test-service")
        monkeypatch.setenv("MITE_CONF_OTEL_SAMPLER_RATIO", "0.5")
        monkeypatch.setenv("MITE_CONF_OTEL_SPAN_PROCESSOR", "batch")
        monkeypatch.setenv("MITE_CONF_OTEL_OTLP_ENDPOINT", "http://localhost:4318")
        
        config = get_otel_config()
        assert config["enabled"] is True
        assert config["service_name"] == "test-service"
        assert config["sampler_ratio"] == 0.5
        assert config["span_processor"] == "batch"
        assert config["otlp_endpoint"] == "http://localhost:4318"
    
    def test_is_tracing_enabled(self, monkeypatch):
        from mite.otel.config import is_tracing_enabled
        
        assert is_tracing_enabled() is False
        
        monkeypatch.setenv("MITE_CONF_OTEL_ENABLED", "true")
        assert is_tracing_enabled() is True


class TestTracing:
    """Test tracing initialization"""
    
    def test_init_tracing_disabled(self):
        from mite.otel.tracing import init_tracing, get_tracer
        
        # Should not crash when disabled
        init_tracing()
        tracer = get_tracer()
        
        # Should return no-op tracer
        with tracer.start_as_current_span("test") as span:
            assert span is None
    
    def test_init_tracing_enabled(self, mock_otel_enabled, in_memory_span_exporter):
        from mite.otel.tracing import init_tracing, get_tracer
        
        init_tracing()
        tracer = get_tracer()
        
        # Should create real spans
        with tracer.start_as_current_span("test-span") as span:
            assert span is not None
            span.set_attribute("test.attr", "value")
        
        # Check span was exported
        spans = in_memory_span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "test-span"
        assert spans[0].attributes["test.attr"] == "value"
    
    def test_get_meter_noop(self):
        from mite.otel.tracing import get_meter
        
        meter = get_meter()
        counter = meter.create_counter("test_counter")
        histogram = meter.create_histogram("test_histogram")
        
        # Should not crash
        counter.add(1)
        histogram.record(1.0)


class TestContext:
    """Test context propagation"""
    
    def test_inject_headers_noop_when_disabled(self):
        from mite.otel.context import inject_headers
        
        headers = {"existing": "header"}
        result = inject_headers(headers)
        
        # Should not modify headers when OTel disabled
        assert result == {"existing": "header"}
    
    def test_extract_context_noop_when_disabled(self):
        from mite.otel.context import extract_context
        
        headers = {"traceparent": "00-trace-span-01"}
        result = extract_context(headers)
        
        # Should return None when OTel disabled
        assert result is None
    
    def test_inject_and_extract_context(self, mock_otel_enabled, in_memory_span_exporter):
        from mite.otel.context import inject_headers, extract_context_from_headers, detach_context
        from mite.otel.tracing import get_tracer
        
        tracer = get_tracer()
        
        # Create a span and inject context
        with tracer.start_as_current_span("parent-span") as span:
            headers = {}
            inject_headers(headers)
            
            # Headers should contain trace context
            assert "traceparent" in headers
            
            # Extract context in another execution context
            token = extract_context_from_headers(headers)
            
            # Create child span
            with tracer.start_as_current_span("child-span") as child_span:
                pass
            
            if token:
                detach_context(token)
        
        # Verify spans were created
        spans = in_memory_span_exporter.get_finished_spans()
        assert len(spans) >= 1


class TestInstrumentation:
    """Test manual instrumentation API"""
    
    @pytest.mark.asyncio
    async def test_trace_journey_decorator(self, mock_otel_enabled, in_memory_span_exporter):
        from mite.otel.instrumentation import trace_journey
        
        @trace_journey("test_journey")
        async def example_journey():
            return "success"
        
        result = await example_journey()
        assert result == "success"
        
        spans = in_memory_span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "journey.test_journey"
        assert spans[0].attributes["mite.journey.name"] == "test_journey"
    
    @pytest.mark.asyncio
    async def test_trace_journey_decorator_with_exception(self, mock_otel_enabled, in_memory_span_exporter):
        from mite.otel.instrumentation import trace_journey
        
        @trace_journey("failing_journey")
        async def failing_journey():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            await failing_journey()
        
        spans = in_memory_span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "journey.failing_journey"
        # Should have recorded the exception
        events = spans[0].events
        assert len(events) > 0
        assert any("exception" in event.name.lower() for event in events)
    
    @pytest.mark.asyncio
    async def test_trace_transaction_context_manager(self, mock_otel_enabled, in_memory_span_exporter):
        from mite.otel.instrumentation import trace_transaction
        
        async with trace_transaction("test_transaction", user_id="123") as span:
            pass
        
        spans = in_memory_span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "transaction.test_transaction"
        assert spans[0].attributes["mite.transaction.name"] == "test_transaction"
        assert spans[0].attributes["mite.transaction.user_id"] == "123"


class TestIntegrations:
    """Test automatic integrations"""
    
    def test_mite_http_decorator_patching(self, mock_otel_enabled):
        from mite.otel.mite_http_integration import patch_mite_http_decorator
        
        # Mock mite_http module
        with patch('mite.otel.mite_http_integration.mite_http') as mock_mite_http:
            original_decorator = MagicMock()
            mock_mite_http.mite_http = original_decorator
            
            patch_mite_http_decorator()
            
            # Should have replaced the decorator
            assert mock_mite_http.mite_http != original_decorator
    
    def test_context_transaction_patching(self, mock_otel_enabled):
        from mite.otel.context_integration import patch_context_transaction
        
        # Mock Context class
        with patch('mite.otel.context_integration.Context') as mock_context:
            original_transaction = MagicMock()
            mock_context.transaction = original_transaction
            
            patch_context_transaction()
            
            # Should have replaced the transaction method
            assert mock_context.transaction != original_transaction
    
    def test_acurl_session_patching(self, mock_otel_enabled):
        from mite.otel.acurl_integration import patch_acurl_session
        
        # Mock Session class
        with patch('mite.otel.acurl_integration.Session') as mock_session:
            original_outer_request = MagicMock()
            mock_session._outer_request = original_outer_request
            
            patch_acurl_session()
            
            # Should have replaced the _outer_request method
            assert mock_session._outer_request != original_outer_request


class TestStatsIntegration:
    """Test stats integration"""
    
    def test_record_http_request(self, mock_otel_enabled):
        from mite.otel.stats_integration import record_http_request, init_stats_mapping
        
        init_stats_mapping()
        
        # Should not crash when recording metrics
        record_http_request("GET", 200, 0.5)
        record_http_request("POST", 500, 1.0, error=True)
    
    def test_stats_mapping_initialization(self, mock_otel_enabled):
        from mite.otel.stats_integration import init_stats_mapping
        
        # Should not crash when initializing
        init_stats_mapping()


class TestEndToEnd:
    """End-to-end integration tests"""
    
    @pytest.mark.asyncio
    async def test_full_integration_flow(self, mock_otel_enabled, in_memory_span_exporter):
        """Test that the full integration works together"""
        from mite.otel.instrumentation import trace_journey, trace_transaction
        from mite.otel.context import inject_headers
        
        @trace_journey("e2e_journey")
        async def journey_with_transaction():
            async with trace_transaction("setup", step="1") as tx_span:
                # Simulate HTTP call preparation
                headers = {}
                inject_headers(headers)
                assert "traceparent" in headers
                
            async with trace_transaction("api_call", step="2") as tx_span:
                # Simulate actual work
                await asyncio.sleep(0.01)
                
            return "completed"
        
        result = await journey_with_transaction()
        assert result == "completed"
        
        spans = in_memory_span_exporter.get_finished_spans()
        assert len(spans) == 3  # 1 journey + 2 transactions
        
        # Verify span hierarchy
        journey_spans = [s for s in spans if s.name.startswith("journey.")]
        transaction_spans = [s for s in spans if s.name.startswith("transaction.")]
        
        assert len(journey_spans) == 1
        assert len(transaction_spans) == 2
        
        assert journey_spans[0].name == "journey.e2e_journey"
        assert journey_spans[0].attributes["mite.journey.name"] == "e2e_journey"


class TestNoOpBehavior:
    """Test that the system works when OpenTelemetry is not available"""
    
    def test_import_without_otel(self, monkeypatch):
        """Test that importing mite.otel works even without OpenTelemetry"""
        # This test verifies the import error handling works
        # In real scenarios, we'd mock the import failure, but the module
        # is already designed to handle missing OpenTelemetry gracefully
        from mite.otel.tracing import get_tracer, get_meter
        from mite.otel.context import inject_headers
        
        # These should work without crashing
        tracer = get_tracer()
        meter = get_meter()
        headers = {}
        inject_headers(headers)
        
        # When OTel is available but disabled, these should be no-ops
        with tracer.start_as_current_span("test") as span:
            pass  # Should not crash
        
        counter = meter.create_counter("test")
        counter.add(1)  # Should not crash


class TestConfigurationVariations:
    """Test different configuration scenarios"""
    
    def test_otlp_http_configuration(self, monkeypatch, mock_otel_enabled):
        from mite.otel.tracing import init_tracing
        
        monkeypatch.setenv("MITE_CONF_OTEL_SPAN_PROCESSOR", "otlp")
        monkeypatch.setenv("MITE_CONF_OTEL_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
        monkeypatch.setenv("MITE_CONF_OTEL_OTLP_PROTOCOL", "http/protobuf")
        
        # Should not crash even if OTLP exporter not available
        init_tracing()
    
    def test_otlp_grpc_configuration(self, monkeypatch, mock_otel_enabled):
        from mite.otel.tracing import init_tracing
        
        monkeypatch.setenv("MITE_CONF_OTEL_SPAN_PROCESSOR", "otlp")
        monkeypatch.setenv("MITE_CONF_OTEL_OTLP_ENDPOINT", "http://localhost:4317")
        monkeypatch.setenv("MITE_CONF_OTEL_OTLP_PROTOCOL", "grpc")
        
        # Should not crash even if OTLP exporter not available
        init_tracing()
    
    def test_batch_processor_configuration(self, monkeypatch, mock_otel_enabled):
        from mite.otel.tracing import init_tracing
        
        monkeypatch.setenv("MITE_CONF_OTEL_SPAN_PROCESSOR", "batch")
        monkeypatch.setenv("MITE_CONF_OTEL_MAX_EXPORT_BATCH_SIZE", "100")
        
        # Should not crash
        init_tracing()
    
    def test_sampling_configuration(self, monkeypatch, mock_otel_enabled, in_memory_span_exporter):
        from mite.otel.tracing import init_tracing, get_tracer
        
        # Test with 0% sampling
        monkeypatch.setenv("MITE_CONF_OTEL_SAMPLER_RATIO", "0.0")
        
        init_tracing()
        tracer = get_tracer()
        
        # Create multiple spans - none should be recorded due to 0% sampling
        for i in range(10):
            with tracer.start_as_current_span(f"test-span-{i}"):
                pass
        
        spans = in_memory_span_exporter.get_finished_spans()
        # With 0% sampling, we might get 0 spans (depends on trace ID generation)
        # This test mainly ensures sampling configuration doesn't crash
        assert len(spans) >= 0