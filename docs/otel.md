# OpenTelemetry Integration

Mite provides optional OpenTelemetry tracing for observing journey execution, transactions, and HTTP requests with minimal code changes.

## Features

- **Explicit decorator** - Use `@mite_http_traced` for journeys you want to trace
- **Zero overhead for non-traced journeys** - `@mite_http` journeys have no tracing overhead
- **Distributed tracing** - Context propagation across HTTP requests  
- **Hierarchical spans** - Journey → Transaction → HTTP request traces
- **Multiple exporters** - Console, OTLP (HTTP/gRPC), Zipkin, Jaeger
- **Configurable sampling** - Control trace volume in production
- **Metrics export** - HTTP request counters and duration histograms
- **Selective instrumentation** - Mix traced and untraced journeys in the same scenario
- **Lazy patching** - Tracing infrastructure only activated when needed

## Installation

```bash
pip install mite[otel]
```

## Quick Start

First, create a simple scenario in `demo_otel.py`:

```python
from mite.otel import mite_http_traced
from mite_http import mite_http
from mite import ensure_average_separation

# This journey will be traced
@mite_http_traced
async def traced_journey(ctx):
    async with ensure_average_separation(1):
        async with ctx.transaction("Get request"):
            await ctx.http.get("https://example.com/")

# This journey will NOT be traced (zero overhead)
@mite_http
async def untraced_journey(ctx):
    async with ensure_average_separation(1):
        await ctx.http.get("https://example.com/health")

scenario = lambda: [
    ("demo_otel:traced_journey", None, lambda s, e: 1),
    ("demo_otel:untraced_journey", None, lambda s, e: 10),
]
```

### 1. Enable Tracing

```bash
export MITE_CONF_OTEL_ENABLED=true
```

This environment variable controls whether tracing is available. When `false`, even `@mite_http_traced` journeys will behave like regular `@mite_http` journeys with no tracing.

### 2. Run Your Test

```bash
mite scenario test demo_otel:scenario --hide-constant-logs
```

**Important:** Only `@mite_http_traced` journeys and their transactions/HTTP requests will be traced. Regular `@mite_http` journeys have zero tracing overhead.

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
- **Transaction spans** - Created for each `ctx.transaction()` call **within traced journeys only**
- **HTTP spans** - Created for each `ctx.http.*()` request **within traced journeys only**

**Note:** Regular `@mite_http` journeys do not create any spans, even when `MITE_CONF_OTEL_ENABLED=true`. This ensures zero overhead for non-traced journeys.

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

You can mix traced and untraced journeys in the same scenario to optimize performance:

```python
from mite.otel import mite_http_traced
from mite_http import mite_http

# This journey will be fully traced (journey, transactions, HTTP requests)
@mite_http_traced
async def critical_journey(ctx):
    async with ctx.transaction("Critical Operation"):
        await ctx.http.post("https://api.example.com/critical")

# This journey will NOT be traced at all (zero overhead)
@mite_http
async def background_journey(ctx):
    async with ctx.transaction("Health Check"):  # No transaction span created
        await ctx.http.get("https://api.example.com/health")  # No HTTP span created

scenario = lambda: [
    ("my_scenario:critical_journey", None, lambda s, e: 1),
    ("my_scenario:background_journey", None, lambda s, e: 10),
]
```

This allows you to:
- Reduce trace volume by only instrumenting critical journeys
- Achieve zero tracing overhead for high-volume background operations
- Control costs when using paid tracing services

### How It Works

When `MITE_CONF_OTEL_ENABLED=true`:
- **`@mite_http_traced` journeys**: Full tracing (journey, transactions, HTTP requests)
- **`@mite_http` journeys**: No tracing at all, zero overhead

When `MITE_CONF_OTEL_ENABLED=false`:
- Both decorators behave identically (no tracing)

The tracing infrastructure uses lazy patching - it only activates when the first `@mite_http_traced` journey is encountered, ensuring minimal impact on startup performance.

## Performance Tuning

### Selective Tracing

The most effective way to reduce overhead is to only trace critical journeys:

```python
from mite.otel import mite_http_traced
from mite_http import mite_http

# Trace only 1 in 10 journeys
@mite_http_traced
async def important_journey(ctx):
    # Full tracing
    pass

# No tracing overhead for these 9
@mite_http
async def regular_journey(ctx):
    # Zero overhead
    pass
```

### Sampling

Control trace volume in production:

```bash
# Only trace 1% of @mite_http_traced journeys
export MITE_CONF_OTEL_SAMPLER_RATIO=0.01
```

### Disabling Tracing

To completely disable tracing (even for `@mite_http_traced` journeys):

```bash
export MITE_CONF_OTEL_ENABLED=false
```

This makes `@mite_http_traced` behave identically to `@mite_http`.

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
