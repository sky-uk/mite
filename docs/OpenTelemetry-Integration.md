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
mite scenario test local.demo:scenario

# mite scenario test demo_otel:scenario
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
journey.my_journey (512ms)
  └── transaction.Login (420ms) 
      ├── HTTP POST (297ms)
      │   ├── http.method: POST
      │   ├── http.url: https://api.example.com/login
      │   ├── http.status_code: 200
      │   └── http.response.header.content-length: 1024
      └── transaction.Get_Profile (124ms)
          └── HTTP GET (123ms)
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
