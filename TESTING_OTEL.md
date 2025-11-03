# Testing OpenTelemetry Integration

This guide shows how to test mite's OpenTelemetry integration locally.

## Quick Start with Docker

### Option 1: Jaeger Only (Recommended)

The simplest way to visualize traces:

```bash
# Start Jaeger
docker-compose -f docker-compose-otel.yml up -d jaeger

# Run the demo with Jaeger export
MITE_CONF_OTEL_ENABLED=true \
MITE_CONF_OTEL_SPAN_PROCESSOR=otlp \
MITE_CONF_OTEL_OTLP_ENDPOINT=http://localhost:4318/v1/traces \
mite scenario test demo_otel_simple:scenario --hide-constant-logs

# Verify traces are arriving
./verify_jaeger.sh

# Open Jaeger UI to view traces
open http://localhost:16686
```

**In the Jaeger UI:**
1. Select `mite-demo` from the Service dropdown
2. Set time range to "Last Hour"  
3. Click "Find Traces"

**Troubleshooting:**
- If traces don't appear in the UI, try hard-refresh (Cmd+Shift+R)
- Verify traces exist: `./verify_jaeger.sh` or check http://localhost:16686/api/services

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
mite scenario test demo_otel_simple:scenario --hide-constant-logs

# View traces
open http://localhost:9411
```

## Testing Without Docker

### Console Output

Simply output traces to the console:

```bash
export MITE_CONF_OTEL_ENABLED=true
export MITE_CONF_OTEL_SERVICE_NAME=mite-console
export MITE_CONF_OTEL_SPAN_PROCESSOR=console

python demo_otel.py
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

## What to Look For

### In Jaeger UI

1. **Service**: Look for your service name (e.g., "mite-demo")
2. **Operations**: Should see journey and transaction operations
3. **Trace Timeline**: Visual representation of span hierarchy
4. **Span Details**: Click on spans to see attributes:
   - `mite.journey.name`
   - `mite.transaction.name`
   - `http.method`, `http.url`, `http.status_code`

### In Console Output

Each span should have:
```json
{
    "name": "journey.demo_user_flow",
    "context": {
        "trace_id": "0x...",
        "span_id": "0x..."
    },
    "attributes": {
        "mite.journey.name": "demo_user_flow"
    }
}
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
export MITE_CONF_OTEL_OTLP_ENDPOINT=https://otel-collector.prod:4318/v1/traces
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

## Troubleshooting

### No traces appearing in Jaeger

1. Check Jaeger is running: `curl http://localhost:16686`
2. Verify mite config: `env | grep MITE_CONF_OTEL`
3. Check console output for errors
4. Try console exporter first: `export MITE_CONF_OTEL_SPAN_PROCESSOR=console`

### Connection refused

- Ensure Docker containers are running: `docker ps`
- Check port conflicts: `lsof -i :4318`
- Try using 127.0.0.1 instead of localhost

### Traces appear incomplete

- Increase export timeout: `export MITE_CONF_OTEL_EXPORT_TIMEOUT=60`
- Check batch size: `export MITE_CONF_OTEL_MAX_EXPORT_BATCH_SIZE=512`
- Review collector logs: `docker logs mite-otel-collector`

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
