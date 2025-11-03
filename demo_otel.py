"""
Demo script showing OpenTelemetry integration working

Usage:
    # Console output (default)
    python demo_otel.py
  
    # Export to Jaeger
    python demo_otel.py jaeger

    # Export to Zipkin
    python demo_otel.py zipkin
"""
import os
import asyncio
import sys

# Determine mode: 'jaeger', 'zipkin', or default (console)
mode = sys.argv[1] if len(sys.argv) > 1 else None

# Set up environment for demo BEFORE importing mite.otel
os.environ["MITE_CONF_OTEL_ENABLED"] = "true"
os.environ["MITE_CONF_OTEL_SERVICE_NAME"] = "mite-demo"
os.environ["MITE_CONF_OTEL_SAMPLER_RATIO"] = "1.0"

if mode == "jaeger":
    os.environ["MITE_CONF_OTEL_SPAN_PROCESSOR"] = "otlp"
    os.environ["MITE_CONF_OTEL_OTLP_ENDPOINT"] = "http://localhost:4318/v1/traces"
    print("🔍 Exporting traces to Jaeger")
    print("   Endpoint: http://localhost:4318/v1/traces")
    print("   View UI: http://localhost:16686")
    print("   Service: mite-demo")
elif mode == "zipkin":
    # Use the Zipkin exporter which posts JSON to /api/v2/spans
    os.environ["MITE_CONF_OTEL_SPAN_PROCESSOR"] = "zipkin"
    os.environ["MITE_CONF_OTEL_OTLP_ENDPOINT"] = "http://localhost:9411/api/v2/spans"
    print("🔍 Exporting traces to Zipkin")
    print("   Endpoint: http://localhost:9411/api/v2/spans")
    print("   View UI: http://localhost:9411")
    print("   Service: mite-demo")
else:
    os.environ["MITE_CONF_OTEL_SPAN_PROCESSOR"] = "console"
    print("📝 Console mode - traces printed below")

# Enable automatic instrumentation - this will auto-initialize due to env vars
import mite.otel

# Import manual instrumentation API
from mite.otel.instrumentation import trace_journey, trace_transaction
from mite.otel.context import inject_headers

print("🚀 OpenTelemetry Integration Demo")
print("=" * 50)

@trace_journey("demo_user_flow")
async def demo_journey():
    """Example journey that demonstrates tracing"""
    print("📝 Starting demo journey...")
    
    async with trace_transaction("login", user_type="test") as span:
        print("  🔐 Simulating login...")
        await asyncio.sleep(0.1)
        
        # Demonstrate context propagation
        headers = {}
        inject_headers(headers)
        if headers:
            print(f"  📡 Injected tracing headers: {list(headers.keys())}")
    
    async with trace_transaction("fetch_data") as span:
        print("  📊 Simulating data fetch...")
        await asyncio.sleep(0.2)
    
    print("✅ Journey completed!")
    return "success"

async def main():
    print("Running demo journey with OpenTelemetry tracing enabled...")
    print("You should see trace spans printed to console below:\n")
    
    result = await demo_journey()
    
    print(f"\n🎉 Demo completed with result: {result}")
    print("\nNote: Trace spans appear above showing the journey hierarchy:")
    print("  journey.demo_user_flow")
    print("    ├── transaction.login")
    print("    └── transaction.fetch_data")

if __name__ == "__main__":
    asyncio.run(main())