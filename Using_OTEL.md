# Mite OpenTelemetry Integration

This guide shows how to use mite's OpenTelemetry integration locally.

## Quick Start with Docker

### Option 1: Jaeger Only

The simplest way to visualize traces:

```bash
# Start Jaeger
docker-compose -f docker-compose-otel.yml up -d jaeger

# Run the demo with Jaeger export
MITE_CONF_OTEL_ENABLED=true \
MITE_CONF_OTEL_SPAN_PROCESSOR=otlp \
MITE_CONF_OTEL_OTLP_ENDPOINT=http://localhost:4318/v1/traces \
mite scenario test demo_otel:scenario --hide-constant-logs

# Open Jaeger UI to view traces
open http://localhost:16686
```

### Option 2: With OpenTelemetry Collector

For advanced scenarios with processing, sampling, and multiple backends:

```bash
# Start Jaeger + Collector
docker-compose -f docker-compose-otel.yml --profile with-collector up -d

# Configure mite to send to collector
export MITE_CONF_OTEL_ENABLED=true
export MITE_CONF_OTEL_SERVICE_NAME=mite-load-test
export MITE_CONF_OTEL_SPAN_PROCESSOR=otlp
export MITE_CONF_OTEL_OTLP_ENDPOINT=http://localhost:4320/v1/traces


# View traces in Jaeger
open http://localhost:16686

# Check collector health
curl http://localhost:13133/
```

### Option 3: Zipkin

Lighter alternative to Jaeger:

```bash
# Start Zipkin
docker-compose -f docker-compose-otel.yml --profile zipkin up -d zipkin

# Run demo
MITE_CONF_OTEL_ENABLED=true \
MITE_CONF_OTEL_SERVICE_NAME=mite-demo \
MITE_CONF_OTEL_SPAN_PROCESSOR=zipkin \
MITE_CONF_OTEL_OTLP_ENDPOINT=http://localhost:9411/api/v2/spans \
mite scenario test demo_otel:scenario --hide-constant-logs

# View traces
open http://localhost:9411
```

## Testing Without Docker

### Console Output

Simply output traces to the console:

```bash
MITE_CONF_OTEL_ENABLED=true \
MITE_CONF_OTEL_SERVICE_NAME=mite-console \
MITE_CONF_OTEL_SPAN_PROCESSOR=console \
mite scenario test demo_otel:scenario --hide-constant-logs
```

You'll see JSON-formatted trace spans in the output.

## Running Tests

```bash
# Install dependencies
pip install mite[otel]

# Run basic tests (no OpenTelemetry required)
python test/test_otel_basic.py

# Run comprehensive test suite
pytest test/test_otel.py -v

# Run all otel tests
pytest test/test_otel*.py -v
```

### Context Propagation

Check that outgoing HTTP requests include the `traceparent` header:

```python
async with ctx.transaction("API Call"):
    # This request will automatically include traceparent header
    await ctx.http.get("https://api.example.com")
```

## Configuration Examples

### Development (100% sampling)
```bash
export MITE_CONF_OTEL_ENABLED=true
export MITE_CONF_OTEL_SERVICE_NAME=mite-dev
export MITE_CONF_OTEL_SAMPLER_RATIO=1.0
export MITE_CONF_OTEL_SPAN_PROCESSOR=otlp
export MITE_CONF_OTEL_OTLP_ENDPOINT=http://localhost:4318/v1/traces
```

### Production (1% sampling)
```bash
export MITE_CONF_OTEL_ENABLED=true
export MITE_CONF_OTEL_SERVICE_NAME=mite-prod
export MITE_CONF_OTEL_SAMPLER_RATIO=0.01
export MITE_CONF_OTEL_SPAN_PROCESSOR=otlp
export MITE_CONF_OTEL_OTLP_ENDPOINT=https://otel-collector:4318/v1/traces
export MITE_CONF_OTEL_OTLP_HEADERS="Authorization=Bearer ${TOKEN}"
export MITE_CONF_OTEL_MAX_EXPORT_BATCH_SIZE=2048
```

### With gRPC
```bash
export MITE_CONF_OTEL_ENABLED=true
export MITE_CONF_OTEL_SERVICE_NAME=mite-grpc
export MITE_CONF_OTEL_SPAN_PROCESSOR=otlp
export MITE_CONF_OTEL_OTLP_ENDPOINT=http://localhost:4317
export MITE_CONF_OTEL_OTLP_PROTOCOL=grpc
```

## Cleanup

```bash
# Stop all containers
docker-compose -f docker-compose-otel.yml down

# Remove volumes
docker-compose -f docker-compose-otel.yml down -v

# Unset environment variables
unset $(env | grep MITE_CONF_OTEL | cut -d= -f1)
```

## Additional Resources

- [Jaeger Documentation](https://www.jaegertracing.io/docs/)
- [OpenTelemetry Collector](https://opentelemetry.io/docs/collector/)
- [OTLP Specification](https://opentelemetry.io/docs/specs/otlp/)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
