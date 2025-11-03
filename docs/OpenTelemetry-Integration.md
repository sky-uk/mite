# OpenTelemetry Integration (Experimental)

## Overview

Mite supports optional OpenTelemetry tracing for observing journey execution, transactions, and HTTP calls made via acurl. This integration provides comprehensive distributed tracing capabilities with minimal code changes.

## Features

- **Automatic instrumentation** - Zero code changes required for existing journeys
- **Distributed tracing** - Context propagation across HTTP requests
- **Journey spans** - Root spans for each `@mite_http` decorated function
- **Transaction spans** - Nested spans for each `ctx.transaction()` call
- **HTTP spans** - Detailed spans for each `ctx.http.*()` request
- **Metrics integration** - Export existing mite stats as OpenTelemetry metrics
- **Multiple exporters** - Console, OTLP HTTP, OTLP gRPC support
- **Configurable sampling** - Control trace volume with sampling ratios

## Installation

```bash
pip install mite[otel]
```

## Quick Start

### 1. Enable Tracing

Set environment variables to enable OpenTelemetry:

```bash
export MITE_CONF_OTEL_ENABLED=true
export MITE_CONF_OTEL_SERVICE_NAME=my-load-test
export MITE_CONF_OTEL_SAMPLER_RATIO=0.1
```

### 2. Import the Module

Add this single line to enable automatic tracing:

```python
import mite.otel  # Enables automatic tracing

from mite_http import mite_http

@mite_http
async def demo_req(ctx):
    async with ctx.transaction("Get request"):
        await ctx.http.get("https://api.example.com/users")
```

### 3. Run Your Test

```bash
python -m mite scenario local.demo:scenario
```

You'll see trace output in the console:

```
{
    "name": "journey.demo_req",
    "context": {
        "trace_id": "0x...",
        "span_id": "0x..."
    },
    "kind": "SpanKind.INTERNAL",
    "parent_id": null,
    "start_time": "2025-10-27T...",
    "end_time": "2025-10-27T...",
    "status": {
        "status_code": "OK"
    },
    "attributes": {
        "mite.journey.name": "demo_req",
        "mite.journey.type": "http"
    }
}
```

## Configuration

All configuration is via environment variables:

### Basic Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MITE_CONF_OTEL_ENABLED` | `false` | Enable/disable tracing |
| `MITE_CONF_OTEL_SERVICE_NAME` | `mite` | Service name in traces |
| `MITE_CONF_OTEL_SAMPLER_RATIO` | `1.0` | Sampling ratio (0.0-1.0) |
| `MITE_CONF_OTEL_SPAN_PROCESSOR` | `console` | Span processor type |

### Span Processors

- `console` - Output traces to console (default)
- `batch` - Batch traces to console 
- `simple` - Simple console output
- `otlp` - Export to OTLP collector

### OTLP Configuration

For production observability platforms (Jaeger, Zipkin, etc.):

| Variable | Default | Description |
|----------|---------|-------------|
| `MITE_CONF_OTEL_OTLP_ENDPOINT` | `""` | OTLP collector endpoint |
| `MITE_CONF_OTEL_OTLP_PROTOCOL` | `http/protobuf` | `http/protobuf` or `grpc` |
| `MITE_CONF_OTEL_OTLP_HEADERS` | `""` | Headers (comma-separated `key=value`) |
| `MITE_CONF_OTEL_MAX_EXPORT_BATCH_SIZE` | `512` | Max spans per batch |
| `MITE_CONF_OTEL_EXPORT_TIMEOUT` | `30` | Export timeout (seconds) |

## Examples

### Console Output (Development)

```bash
export MITE_CONF_OTEL_ENABLED=true
export MITE_CONF_OTEL_SERVICE_NAME=mite-dev
export MITE_CONF_OTEL_SAMPLER_RATIO=1.0
export MITE_CONF_OTEL_SPAN_PROCESSOR=console

python -m mite scenario local.demo:scenario
```

### Jaeger (Production)

```bash
export MITE_CONF_OTEL_ENABLED=true
export MITE_CONF_OTEL_SERVICE_NAME=mite-load-test
export MITE_CONF_OTEL_SAMPLER_RATIO=0.1
export MITE_CONF_OTEL_SPAN_PROCESSOR=otlp
export MITE_CONF_OTEL_OTLP_ENDPOINT=http://jaeger:4318/v1/traces

python -m mite scenario local.demo:scenario
```

### Zipkin with Authentication

```bash
export MITE_CONF_OTEL_ENABLED=true
export MITE_CONF_OTEL_SERVICE_NAME=mite-prod
export MITE_CONF_OTEL_SAMPLER_RATIO=0.05
export MITE_CONF_OTEL_SPAN_PROCESSOR=otlp
export MITE_CONF_OTEL_OTLP_ENDPOINT=https://zipkin.company.com/api/v2/spans
export MITE_CONF_OTEL_OTLP_HEADERS="Authorization=Bearer token123,X-Custom=value"

python -m mite scenario local.demo:scenario
```

### OTLP gRPC

```bash
export MITE_CONF_OTEL_ENABLED=true
export MITE_CONF_OTEL_SERVICE_NAME=mite-grpc
export MITE_CONF_OTEL_SPAN_PROCESSOR=otlp
export MITE_CONF_OTEL_OTLP_ENDPOINT=http://collector:4317
export MITE_CONF_OTEL_OTLP_PROTOCOL=grpc

python -m mite scenario local.demo:scenario
```

## Trace Structure

The automatic instrumentation creates a hierarchical trace structure:

```
journey.my_journey (10.2s)
  └── transaction.Login (8.1s) 
      ├── HTTP POST (2.1s)
      │   ├── http.method: POST
      │   ├── http.url: https://api.example.com/login
      │   ├── http.status_code: 200
      │   └── http.response.header.content-length: 1024
      └── transaction.Get_Profile (5.8s)
          └── HTTP GET (5.7s)
              ├── http.method: GET
              ├── http.url: https://api.example.com/profile
              ├── http.status_code: 200
              └── http.response.header.content-length: 2048
```

## Manual Instrumentation (Advanced)

For custom spans or when automatic instrumentation isn't sufficient:

```python
import mite.otel
from mite.otel import trace_journey, trace_transaction

@trace_journey("custom_journey")  # Override automatic naming
async def my_journey(ctx):
    async with trace_transaction("custom_setup", user_id="123") as span:
        # Custom logic here
        if span:
            span.set_attribute("custom.attribute", "value")
```

## Distributed Tracing

HTTP requests automatically include distributed tracing headers:

```python
@mite_http
async def service_a(ctx):
    async with ctx.transaction("Call Service B"):
        # This request will include traceparent header automatically
        await ctx.http.post("https://service-b.com/api", json={"data": "test"})
```

Service B can extract the trace context to continue the distributed trace.

## Performance Considerations

### Sampling

Use sampling to control trace volume in production:

```bash
# Only trace 1% of requests
export MITE_CONF_OTEL_SAMPLER_RATIO=0.01
```

### Batch Processing

Use batch processing to reduce overhead:

```bash
# Batch spans before sending
export MITE_CONF_OTEL_SPAN_PROCESSOR=batch
export MITE_CONF_OTEL_MAX_EXPORT_BATCH_SIZE=1000
```

### Memory Usage

- Spans are held in memory until exported
- Reduce `MAX_EXPORT_BATCH_SIZE` for memory-constrained environments
- Consider using `simple` processor for immediate export

## Metrics Integration (Experimental)

Existing mite stats are automatically exported as OpenTelemetry metrics when tracing is enabled:

- `mite_requests_total` - Counter of HTTP requests by method/status
- `mite_request_duration_seconds` - Histogram of request durations
- `mite_active_journeys` - Current number of active journeys

## Troubleshooting

### No Traces Appearing

Check that:
1. `MITE_CONF_OTEL_ENABLED=true` is set
2. OpenTelemetry libraries are installed: `pip install mite[otel]`
3. `import mite.otel` is called before journey execution
4. Sampling ratio > 0: `MITE_CONF_OTEL_SAMPLER_RATIO=1.0`

### OTLP Export Errors

```bash
# Test with console output first
export MITE_CONF_OTEL_SPAN_PROCESSOR=console

# Check collector connectivity
curl -X POST http://jaeger:4318/v1/traces \
  -H "Content-Type: application/json" \
  -d '{}'
```

### High Memory Usage

```bash
# Reduce batch size
export MITE_CONF_OTEL_MAX_EXPORT_BATCH_SIZE=100

# Use simple processor
export MITE_CONF_OTEL_SPAN_PROCESSOR=simple

# Reduce sampling
export MITE_CONF_OTEL_SAMPLER_RATIO=0.01
```

### Import Errors

The integration gracefully handles missing OpenTelemetry libraries:

```python
# Safe to import even without [otel] extras
import mite.otel

# All functions become no-ops if libraries missing
from mite.otel import trace_journey  # Won't crash
```

## Example Journey with Full Instrumentation

```python
import mite.otel  # Enable automatic tracing

from mite_http import mite_http
from mite.otel import trace_transaction  # For custom spans

@mite_http
async def user_registration_flow(ctx):
    """Complete user registration journey with tracing"""
    
    # Automatic transaction span
    async with ctx.transaction("Create User Account"):
        response = await ctx.http.post("/api/users", json={
            "username": "testuser",
            "email": "test@example.com"
        })
        user_id = response.json()["id"]
    
    # Custom transaction span with attributes
    async with trace_transaction("Send Welcome Email", user_id=user_id):
        await ctx.http.post("/api/emails", json={
            "to": "test@example.com",
            "template": "welcome",
            "user_id": user_id
        })
    
    # Nested transactions
    async with ctx.transaction("Setup User Profile"):
        async with ctx.transaction("Upload Avatar"):
            await ctx.http.post(f"/api/users/{user_id}/avatar", 
                              data=b"fake-image-data")
        
        async with ctx.transaction("Set Preferences"):
            await ctx.http.put(f"/api/users/{user_id}/preferences", json={
                "theme": "dark",
                "notifications": True
            })
    
    return f"User {user_id} registered successfully"

def scenario():
    return [
        ["local.demo:user_registration_flow", None, lambda s, e: 5]
    ]
```

This journey will produce a rich trace showing:
- Root span: `journey.user_registration_flow`
- Child spans: `transaction.Create_User_Account`, `transaction.Send_Welcome_Email`, etc.
- HTTP spans: `HTTP POST`, `HTTP PUT` with full request/response details
- Custom attributes: `user_id`, `mite.transaction.*` attributes
- Distributed tracing headers in all HTTP requests

## Security Considerations

- Trace data may contain sensitive information from HTTP requests/responses
- Consider sampling and filtering strategies for production
- Secure your OTLP endpoints with authentication
- Be aware that traces traverse network boundaries

## Testing with OpenTelemetry

### Local Testing with Docker

The easiest way to test the OpenTelemetry integration is using Docker containers for the observability backend.

#### Option 1: Jaeger All-in-One (Recommended for Development)

Jaeger provides an all-in-one Docker image with collector, storage, and UI:

```bash
# Start Jaeger
docker run -d --name jaeger \
  -e COLLECTOR_OTLP_ENABLED=true \
  -p 16686:16686 \
  -p 4317:4317 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest

# Configure mite to send traces to Jaeger
export MITE_CONF_OTEL_ENABLED=true
export MITE_CONF_OTEL_SERVICE_NAME=mite-test
export MITE_CONF_OTEL_SPAN_PROCESSOR=otlp
export MITE_CONF_OTEL_OTLP_ENDPOINT=http://localhost:4318/v1/traces
export MITE_CONF_OTEL_OTLP_PROTOCOL=http/protobuf

# Run your mite tests
python -m mite scenario local.demo:scenario

# View traces in Jaeger UI
open http://localhost:16686
```

**Jaeger UI Features:**
- Search traces by service, operation, tags
- Visualize trace timelines and spans
- Compare traces for performance analysis
- View span attributes and logs

#### Option 2: OpenTelemetry Collector + Jaeger

For more control, use the OpenTelemetry Collector with Jaeger backend:

**docker-compose.yml:**
```yaml
version: '3'
services:
  # Jaeger backend
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # Jaeger UI
      - "14250:14250"  # Jaeger gRPC
    environment:
      - COLLECTOR_OTLP_ENABLED=true

  # OpenTelemetry Collector
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
      - "8888:8888"   # Prometheus metrics
      - "13133:13133" # Health check
    depends_on:
      - jaeger
```

**otel-collector-config.yaml:**
```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 10s
    send_batch_size: 1024
  
  memory_limiter:
    check_interval: 1s
    limit_mib: 512

exporters:
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true
  
  logging:
    loglevel: debug

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [jaeger, logging]
```

**Usage:**
```bash
# Start the stack
docker-compose up -d

# Configure mite
export MITE_CONF_OTEL_ENABLED=true
export MITE_CONF_OTEL_SERVICE_NAME=mite-test
export MITE_CONF_OTEL_SPAN_PROCESSOR=otlp
export MITE_CONF_OTEL_OTLP_ENDPOINT=http://localhost:4318/v1/traces

# Run tests
python demo_otel.py

# View traces
open http://localhost:16686

# Check collector health
curl http://localhost:13133/

# Stop the stack
docker-compose down
```

#### Option 3: Zipkin (Lightweight Alternative)

Zipkin is a simpler alternative to Jaeger:

```bash
# Start Zipkin
docker run -d --name zipkin \
  -p 9411:9411 \
  openzipkin/zipkin:latest

# Configure mite for Zipkin
export MITE_CONF_OTEL_ENABLED=true
export MITE_CONF_OTEL_SERVICE_NAME=mite-test
export MITE_CONF_OTEL_SPAN_PROCESSOR=otlp
export MITE_CONF_OTEL_OTLP_ENDPOINT=http://localhost:9411/api/v2/spans
export MITE_CONF_OTEL_OTLP_PROTOCOL=http/protobuf

# Run tests
python -m mite scenario local.demo:scenario

# View traces
open http://localhost:9411
```

### Running the Demo

The repository includes a working demo that shows OpenTelemetry tracing:

```bash
# Ensure OpenTelemetry is installed
pip install mite[otel]

# Run the demo (outputs traces to console)
python demo_otel.py

# Or with Jaeger
docker run -d --name jaeger \
  -e COLLECTOR_OTLP_ENABLED=true \
  -p 16686:16686 -p 4318:4318 \
  jaegertracing/all-in-one:latest

export MITE_CONF_OTEL_ENABLED=true
export MITE_CONF_OTEL_SPAN_PROCESSOR=otlp
export MITE_CONF_OTEL_OTLP_ENDPOINT=http://localhost:4318/v1/traces

python demo_otel.py

# View in Jaeger UI
open http://localhost:16686
```

### Running Tests

```bash
# Install test dependencies
pip install mite[otel]

# Run basic tests (no OpenTelemetry required)
python test/test_otel_basic.py

# Run comprehensive tests (requires OpenTelemetry)
pytest test/test_otel.py -v

# Run with coverage
pytest test/test_otel.py --cov=mite.otel --cov-report=html
```

### Verifying the Integration

1. **Console Output**: Set `MITE_CONF_OTEL_SPAN_PROCESSOR=console` to see traces in stdout
2. **Check Spans**: Verify span names follow the pattern:
   - `journey.<function_name>` for journey spans
   - `transaction.<name>` for transaction spans
   - `HTTP <METHOD>` for HTTP request spans
3. **Verify Attributes**: Check spans contain:
   - `mite.journey.name`
   - `mite.transaction.name`
   - `http.method`, `http.url`, `http.status_code`
4. **Test Context Propagation**: Verify `traceparent` headers in outgoing requests
5. **Check Hierarchy**: Parent-child relationships should be correct

### Production Deployment Tips

When deploying with OpenTelemetry in production:

1. **Use the OpenTelemetry Collector** as a sidecar or daemonset
2. **Configure sampling** to reduce trace volume (0.01 = 1% sampling)
3. **Set up batching** to reduce network overhead
4. **Use authentication** for OTLP endpoints in production
5. **Monitor collector health** and resource usage
6. **Configure retry logic** for transient network failures

Example production configuration:
```bash
export MITE_CONF_OTEL_ENABLED=true
export MITE_CONF_OTEL_SERVICE_NAME=mite-prod-loadtest
export MITE_CONF_OTEL_SPAN_PROCESSOR=otlp
export MITE_CONF_OTEL_OTLP_ENDPOINT=http://otel-collector:4318/v1/traces
export MITE_CONF_OTEL_SAMPLER_RATIO=0.01  # 1% sampling
export MITE_CONF_OTEL_MAX_EXPORT_BATCH_SIZE=2048
export MITE_CONF_OTEL_EXPORT_TIMEOUT=60
export MITE_CONF_OTEL_OTLP_HEADERS="Authorization=Bearer ${API_TOKEN}"
```

## Limitations

- Cython-based acurl integration uses response callbacks (slight delay in span completion)
- Automatic patching may conflict with other instrumentation libraries
- Some advanced OpenTelemetry features (baggage, links) not yet supported
- Metrics integration is basic and experimental

## Future Enhancements

- Baggage propagation for request-scoped data
- More granular HTTP span attributes (request/response sizes, etc.)
- Integration with mite's volume model for load-aware sampling
- Custom span processors for mite-specific needs
- Support for OpenTelemetry logging integration