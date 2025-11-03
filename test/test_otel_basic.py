"""
Simple test to demonstrate OpenTelemetry integration works
"""
import os
import asyncio

def test_otel_import_when_disabled():
    """Test that mite.otel can be imported when disabled (default)"""
    # Ensure OTel is disabled
    os.environ["MITE_CONF_OTEL_ENABLED"] = "false"
    
    # Should not crash
    from mite.otel.config import get_otel_config, is_tracing_enabled
    from mite.otel.tracing import get_tracer, get_meter
    from mite.otel.context import inject_headers
    
    config = get_otel_config()
    assert not config["enabled"]
    assert not is_tracing_enabled()
    
    # These should return no-op objects
    tracer = get_tracer()
    meter = get_meter()
    
    # Should not crash
    with tracer.start_as_current_span("test") as span:
        assert span is None
    
    counter = meter.create_counter("test")
    counter.add(1)
    
    headers = {}
    inject_headers(headers)
    # Should not add headers when disabled
    assert len(headers) == 0

def test_otel_config_from_env():
    """Test configuration from environment variables"""
    from mite.otel.config import get_otel_config
    
    # Set test environment
    os.environ["MITE_CONF_OTEL_ENABLED"] = "true"
    os.environ["MITE_CONF_OTEL_SERVICE_NAME"] = "test-service"
    os.environ["MITE_CONF_OTEL_SAMPLER_RATIO"] = "0.5"
    os.environ["MITE_CONF_OTEL_SPAN_PROCESSOR"] = "batch"
    
    config = get_otel_config()
    assert config["enabled"] is True
    assert config["service_name"] == "test-service"
    assert config["sampler_ratio"] == 0.5
    assert config["span_processor"] == "batch"
    
    # Clean up
    os.environ["MITE_CONF_OTEL_ENABLED"] = "false"

def test_manual_instrumentation_api():
    """Test manual instrumentation API works without OTel installed"""
    from mite.otel.instrumentation import trace_journey, trace_transaction
    
    @trace_journey("test_journey")
    async def test_func():
        async with trace_transaction("test_tx") as span:
            return "success"
    
    # Should not crash even without OpenTelemetry
    result = asyncio.run(test_func())
    assert result == "success"

def test_integration_patches():
    """Test that integration patches don't crash"""
    os.environ["MITE_CONF_OTEL_ENABLED"] = "true"
    
    from mite.otel.mite_http_integration import patch_mite_http_decorator
    from mite.otel.context_integration import patch_context_transaction
    from mite.otel.acurl_integration import patch_acurl_session
    from mite.otel.stats_integration import init_stats_mapping
    
    # These should not crash even if target modules don't exist
    patch_mite_http_decorator()
    patch_context_transaction()
    patch_acurl_session()
    init_stats_mapping()
    
    # Clean up
    os.environ["MITE_CONF_OTEL_ENABLED"] = "false"

if __name__ == "__main__":
    print("Running basic OpenTelemetry integration tests...")
    
    test_otel_import_when_disabled()
    print("✓ Import test passed")
    
    test_otel_config_from_env()
    print("✓ Configuration test passed")
    
    test_manual_instrumentation_api()
    print("✓ Manual instrumentation test passed")
    
    test_integration_patches()
    print("✓ Integration patches test passed")
    
    print("\nAll tests passed! 🎉")
    print("\nTo test with actual OpenTelemetry:")
    print("1. pip install mite[otel]")
    print("2. export MITE_CONF_OTEL_ENABLED=true")
    print("3. python -m pytest test/test_otel.py -v")