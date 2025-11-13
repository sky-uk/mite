# Memory Tuning Guide for acurl

## HTTP/2 Connection Pool Configuration

### Background

The `CURL_LOCK_DATA_CONNECT` fix enables proper HTTP/2 connection sharing, which increases memory usage due to persistent connection pooling. Each HTTP/2 connection maintains state (stream tracking, flow control windows, HPACK compression) that consumes approximately 20-50KB per connection.

### Configuration Options

#### Option 1: Default Behavior (Recommended)

No configuration needed - uses default of 100 connections (~2-5MB overhead):

```python
from mite_http import mite_http

@mite_http
async def my_journey(ctx):
    await ctx.http.get("https://example.com")
```

#### Option 2: Memory-Constrained Environments

For 512MB containers, reduce connection pool size:

```python
from mite_http import mite_http

@mite_http(max_connects=50)  # Or 25 for very tight constraints
async def my_journey(ctx):
    await ctx.http.get("https://example.com")
```

#### Option 3: High-Throughput Scenarios

For applications with many unique hosts or high concurrency:

```python
from mite_http import mite_http

@mite_http(max_connects=200)
async def my_journey(ctx):
    await ctx.http.get("https://example.com")
```

#### Option 4: Direct SessionPool Configuration

For advanced use cases:

```python
from mite_http import SessionPool

# Create a custom session pool
pool = SessionPool(max_connects=50)

# Use it directly
async with pool.session_context(ctx):
    await ctx.http.get("https://example.com")
```

### Memory Guidelines

| Container Memory | Recommended max_connects | Estimated Overhead |
|------------------|-------------------------|-------------------|
| 512 MB          | 25-50                   | 1-2 MB            |
| 1 GB            | 50-100                  | 2-5 MB            |
| 2 GB+           | 100-200 (default: 100)  | 5-10 MB           |

### Troubleshooting

**Symptom**: OOMKilled in containerized environments
- **Solution**: Reduce `max_connects` to 25-50

**Symptom**: Frequent reconnections or performance degradation
- **Solution**: Increase `max_connects` to 200+

**Symptom**: HTTP/2 stream errors (code 92)
- **Solution**: Ensure using the fixed version with `CURL_LOCK_DATA_CONNECT`

### Technical Details

The connection pool (`CURLMOPT_MAXCONNECTS`) limits how many idle connections libcurl maintains. With HTTP/2:
- Connections are multiplexed (multiple requests per connection)
- Connections persist across requests
- Each connection has fixed overhead regardless of active streams
- Lower limits mean more reconnections but less memory
- Higher limits mean fewer reconnections but more memory

Default of 100 provides good balance for most scenarios.
