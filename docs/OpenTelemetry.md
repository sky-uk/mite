# OpenTelemetry Integration

Mite provides optional OpenTelemetry tracing for observing journey execution, transactions, and HTTP requests with minimal code changes.

## Features

- **Explicit decorator** - Use `@mite_http_traced` for journeys you want to trace
- **Distributed tracing** - Context propagation across HTTP requests  
- **Hierarchical spans** - Journey → Transaction → HTTP request traces
- **Multiple exporters** - Console, OTLP (HTTP/gRPC), Zipkin, Jaeger
- **Configurable sampling** - Control trace volume in production
- **Metrics export** - HTTP request counters and duration histograms
- **Selective instrumentation** - Mix traced and untraced journeys in the same scenario

## Installation

```bash
pip install mite[otel]
```

## Quick Start


First, create a simple scenario in `demo_otel.py`:

```python
from mite.otel import mite_http_traced
from mite import ensure_average_separation

@mite_http_traced
async def demo_req(ctx):
    async with ensure_average_separation(1):
        async with ctx.transaction("Get request"):
            await ctx.http.get("https://example.com/")

scenario = lambda: [("demo_otel:demo_req", None, lambda s, e: 2)]
```

### 1. Enable Tracing

```bash
export MITE_CONF_OTEL_ENABLED=true
```

### 2. Run Your Test

```bash
mite scenario test demo_otel:scenario --hide-constant-logs
```

Use `@mite_http_traced` instead of `@mite_http` for journeys you want to trace.

### 3. View Traces

Traces are printed to console by default. For visualization, use Jaeger or Zipkin (see below).

## Configuration

All settings are controlled via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MITE_CONF_OTEL_ENABLED` | `false` | Enable/disable tracing |
| `MITE_CONF_OTEL_SERVICE_NAME` | `mite` | Service name in traces |
| `MITE_CONF_OTEL_SAMPLER_RATIO` | `1.0` | Sampling rate (0.0-1.0) |
| `MITE_CONF_OTEL_SPAN_PROCESSOR` | `console` | `console`, `batch`, `otlp`, `zipkin` |
| `MITE_CONF_OTEL_OTLP_ENDPOINT` | `""` | OTLP collector/backend URL |
| `MITE_CONF_OTEL_OTLP_PROTOCOL` | `http/protobuf` | `http/protobuf` or `grpc` |
| `MITE_CONF_OTEL_OTLP_HEADERS` | `""` | Comma-separated `key=value` pairs |
| `MITE_CONF_OTEL_MAX_EXPORT_BATCH_SIZE` | `512` | Max spans per batch |
| `MITE_CONF_OTEL_EXPORT_TIMEOUT` | `30` | Export timeout (seconds) |

## Usage Examples

### Console Output

```bash
MITE_CONF_OTEL_ENABLED=true \
MITE_CONF_OTEL_SPAN_PROCESSOR=console \
mite scenario test demo_otel:scenario --hide-constant-logs
```

### Jaeger

```bash
# Start: docker run -d -p 16686:16686 -p 4318:4318 jaegertracing/all-in-one
MITE_CONF_OTEL_ENABLED=true \
MITE_CONF_OTEL_SPAN_PROCESSOR=otlp \
MITE_CONF_OTEL_OTLP_ENDPOINT=http://localhost:4318/v1/traces \
mite scenario test demo_otel:scenario --hide-constant-logs
# View: http://localhost:16686
```

### Zipkin

```bash
# Start: docker run -d -p 9411:9411 openzipkin/zipkin
MITE_CONF_OTEL_ENABLED=true \
MITE_CONF_OTEL_SPAN_PROCESSOR=zipkin \
MITE_CONF_OTEL_OTLP_ENDPOINT=http://localhost:9411/api/v2/spans \
mite scenario test demo_otel:scenario --hide-constant-logs
# View: http://localhost:9411
```

### 1% sampling, authenticated

```bash
MITE_CONF_OTEL_ENABLED=true \
MITE_CONF_OTEL_SAMPLER_RATIO=0.01 \
MITE_CONF_OTEL_SPAN_PROCESSOR=otlp \
MITE_CONF_OTEL_OTLP_ENDPOINT=https://collector.company.com:4318/v1/traces \
MITE_CONF_OTEL_OTLP_HEADERS="Authorization=Bearer ${API_KEY}" \
mite scenario test production:scenario --hide-constant-logs
```

## Trace Structure

Mite automatically creates hierarchical traces:

```
journey.user_login (520ms)
  └── transaction.Login (450ms)
      ├── HTTP POST /auth/login (280ms)
      │   ├── http.method: POST
      │   ├── http.url: https://api.example.com/auth/login
      │   ├── http.status_code: 200
      │   └── http.response.time.total: 0.28
      └── transaction.Fetch_Profile (170ms)
          └── HTTP GET /users/me (169ms)
              ├── http.method: GET
              ├── http.status_code: 200
              └── http.response.body.size: 2048
```

### Span Types

- **Journey spans** - Created for each `@mite_http_traced` decorated function
- **Transaction spans** - Created for each `ctx.transaction()` call
- **HTTP spans** - Created for each `ctx.http.*()` request

## Distributed Tracing

HTTP requests automatically include W3C `traceparent` headers for distributed tracing:

```python
from mite.otel import mite_http_traced

@mite_http_traced
async def call_downstream_service(ctx):
    async with ctx.transaction("Call Service B"):
        # Automatically includes traceparent header
        response = await ctx.http.post(
            "https://service-b.com/api",
            json={"data": "test"}
        )
```

The downstream service can extract the trace context to continue the distributed trace.

## Manual Instrumentation

For custom spans or advanced use cases:

```python
from mite.otel import trace_journey, trace_transaction

# Custom journey decorator
@trace_journey("custom_journey_name")
async def my_journey(ctx):
    # Custom transaction with attributes
    async with trace_transaction("database_query", table="users") as span:
        if span:
            span.set_attribute("query.rows", 150)
        # Your logic here
```

## Selective Instrumentation

You can mix traced and untraced journeys in the same scenario:

```python
from mite.otel import mite_http_traced
from mite_http import mite_http

# This journey will be traced
@mite_http_traced
async def critical_journey(ctx):
    async with ctx.transaction("Critical Operation"):
        await ctx.http.post("https://api.example.com/critical")

# This journey will NOT be traced
@mite_http
async def background_journey(ctx):
    await ctx.http.get("https://api.example.com/health")

scenario = lambda: [
    ("my_scenario:critical_journey", None, lambda s, e: 1),
    ("my_scenario:background_journey", None, lambda s, e: 10),
]
```

This allows you to reduce trace volume by only instrumenting the journeys that matter most.

## Performance Tuning

### Sampling

Control trace volume in production:

```bash
# Only trace 1% of requests
export MITE_CONF_OTEL_SAMPLER_RATIO=0.01
```

### Batch Size

Adjust for memory vs latency tradeoff:

```bash
# Smaller batches = less memory, more frequent exports
export MITE_CONF_OTEL_MAX_EXPORT_BATCH_SIZE=100

# Larger batches = more memory, fewer exports
export MITE_CONF_OTEL_MAX_EXPORT_BATCH_SIZE=2048
```

### Processor Selection

- `console` - Immediate output, good for debugging
- `batch` - Batched exports, better for production
- `otlp` - OTLP protocol with batching
- `zipkin` - Zipkin-specific format with batching


## Resources

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Jaeger](https://www.jaegertracing.io/)
- [Zipkin](https://zipkin.io/)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
