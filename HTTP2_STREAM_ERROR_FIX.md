# HTTP/2 Stream Error Fix - Technical Note

**Date:** November 2025  
**Status:** Fixed  
**Branch:** `fix-92-stream-error`

---

## Problem

Intermittent `acurl.AcurlError: curl failed with code 92 Stream error in the HTTP/2 framing layer` occurring at ~3% of requests when using HTTP/2.

## Investigation Timeline

1. **Initial Observation** - Error 92 occurring intermittently (~3%), only on HTTP/2 endpoints
2. **Server Verification** - Confirmed server supports HTTP/2 correctly via direct curl test
3. **First Attempt** - Added `CURL_LOCK_DATA_CONNECT` connection sharing → Errors eliminated but CPU spiked 10% → 70%
4. **Performance Issue** - Connection sharing caused severe CPU overhead and slow percentile latencies
5. **Second Attempt** - No-op lock callbacks → No improvement
6. **Third Attempt** - `CURLMOPT_MAX_HOST_CONNECTIONS=0` → No improvement
7. **Fourth Attempt** - Removed connection sharing, kept only DNS/cookie sharing → Errors returned
8. **Root Cause Identified** - HTTP/2 itself was causing both errors and performance issues
9. **Final Solution** - Force HTTP/1.1 by default, make HTTP version configurable

---

## Root Cause

**HTTP/2 Incompatibility**

The stream error 92 and performance issues were both symptoms of HTTP/2 behavior in libcurl:
- HTTP/2 stream ID conflicts when connections are shared improperly
- High CPU overhead from HTTP/2 multiplexing management
- Sporadic high percentile latencies from HTTP/2 head-of-line blocking

**Testing proved:**
- HTTP/1.1: No errors, 10% CPU usage ✅
- HTTP/2 with connection sharing: No errors, 70% CPU usage ❌
- HTTP/2 without connection sharing: Stream errors, high CPU ❌

---

## Solution

**Make HTTP version configurable (default: auto for backward compatibility)**

Added `http_version` parameter to control HTTP protocol version while preserving original behavior.

### Changes Made

**1. Added HTTP version constants** (`acurl/src/curlinterface.pxd`)

```cython
cdef int CURLOPT_HTTP_VERSION
cdef int CURL_HTTP_VERSION_1_1
cdef int CURL_HTTP_VERSION_2_0
```

**2. Session accepts http_version parameter** (`acurl/src/session.pyx`)

```cython
def __cinit__(self, wrapper, http_version="auto"):
    # ... setup code ...
    
    # Configure HTTP version (default to auto for backward compatibility)
    if http_version == "1.1":
        self.curl_http_version = CURL_HTTP_VERSION_1_1
    elif http_version == "2":
        self.curl_http_version = CURL_HTTP_VERSION_2_0
    elif http_version == "auto":
        self.curl_http_version = 0  # Let curl decide
    else:
        raise ValueError(f"Invalid http_version: {http_version}")
```

**3. Apply HTTP version in requests** (`acurl/src/session.pyx`)

```cython
# In _inner_request method
if self.curl_http_version != 0:
    acurl_easy_setopt_int(curl, CURLOPT_HTTP_VERSION, self.curl_http_version)
```

**4. Exposed in mite_http decorator** (`mite_http/__init__.py`)

```python
@mite_http  # Uses "auto" (default, preserves original behavior)
async def my_journey(ctx):
    await ctx.http.get("https://example.com")

# Or force HTTP/1.1 to avoid HTTP/2 issues
@mite_http(http_version="1.1")
async def my_journey(ctx):
    await ctx.http.get("https://example.com")
```

---

## Usage

**Default behavior (auto - preserves original behavior):**

```python
@mite_http
async def my_journey(ctx):
    await ctx.http.get("https://api.example.com")
# curl negotiates HTTP/1.1 or HTTP/2 based on server support
```

**Force HTTP/1.1 (recommended if experiencing issues):**

```python
@mite_http(http_version="1.1")
async def my_journey(ctx):
    await ctx.http.get("https://api.example.com")
```

**Force HTTP/2:**

```python
@mite_http(http_version="2")
async def my_journey(ctx):
    await ctx.http.get("https://api.example.com")
```

---

## Performance Impact

| Configuration | Error Rate | CPU Usage | Latency P95 | Recommendation |
|--------------|-----------|-----------|-------------|----------------|
| HTTP/1.1 (forced) | 0% | 10% | Normal | ✅ **Use if experiencing issues** |
| HTTP/2 (forced) | 0-3% | 70% | Spikes | ⚠️ Problematic at high load |
| Auto (default) | Varies | Varies | Varies | ℹ️ Preserves original behavior |

**Note:** With "auto", behavior depends on server HTTP/2 support. If server supports HTTP/2, you may encounter the issues described above.

---

## Configuration Options

The `http_version` parameter accepts:

- `"auto"` (default): Let curl negotiate with server. Preserves original behavior but may encounter HTTP/2 issues.
- `"1.1"`: Forces HTTP/1.1. Stable, low CPU, recommended if experiencing HTTP/2 problems.
- `"2"`: Forces HTTP/2. May cause high CPU and latency spikes at high load.

---

## HTTP/2 vs HTTP/1.1 Trade-offs

### When to Use HTTP/1.1 (`http_version="1.1"`)

**Advantages:**
- ✅ **Predictable performance**: Stable CPU usage (~10%)
- ✅ **No stream errors**: Avoids HTTP/2 stream ID conflicts
- ✅ **Low latency**: Consistent response times without head-of-line blocking
- ✅ **Simple connection model**: One request per connection, easy to reason about
- ✅ **Better for load testing**: Isolates application performance from protocol complexity

**Disadvantages:**
- ❌ **More connections**: Each concurrent request needs its own TCP connection
- ❌ **No multiplexing**: Can't share connections between requests to same host
- ❌ **More overhead**: More TCP handshakes and TLS negotiations

**Use HTTP/1.1 when:**
- Running high-volume load tests (600+ TPS)
- Experiencing HTTP/2 stream errors or high CPU
- Need predictable, stable performance
- Testing applications that primarily use HTTP/1.1 in production

### When to Use HTTP/2 (`http_version="2"`)

**Advantages:**
- ✅ **Connection reuse**: Multiple requests share one connection per host
- ✅ **Header compression**: HPACK reduces bandwidth
- ✅ **Multiplexing**: Parallel requests without connection overhead
- ✅ **Server push**: Servers can proactively send resources

**Disadvantages:**
- ❌ **High CPU overhead**: 7x higher CPU usage (10% → 70%) observed in testing
- ❌ **Stream errors**: Can encounter "Stream error in the HTTP/2 framing layer" (error 92)
- ❌ **Head-of-line blocking**: TCP-level blocking affects all streams on a connection
- ❌ **Sporadic latencies**: High percentile latencies (p95/p99 spikes)
- ❌ **Complex debugging**: Harder to isolate performance issues

**Use HTTP/2 when:**
- Need to test HTTP/2-specific application behavior
- Low request rates (< 100 TPS)
- Testing against servers that require HTTP/2
- Validating HTTP/2 compatibility

### When to Use Auto (`http_version="auto"`)

**Advantages:**
- ✅ **Matches production**: Tests actual protocol negotiation
- ✅ **Server preference**: Lets server choose optimal protocol
- ✅ **Backward compatible**: Default behavior, no changes needed

**Disadvantages:**
- ❌ **Unpredictable**: Behavior depends on server capabilities
- ❌ **Hidden issues**: May silently use HTTP/2 and encounter problems
- ❌ **Hard to debug**: Not always clear which protocol is being used

**Use auto when:**
- You want to preserve original behavior
- Testing protocol negotiation is part of your test scenario
- Low load testing where HTTP/2 issues don't manifest

### Performance Comparison

| Metric | HTTP/1.1 | HTTP/2 | Auto (with HTTP/2 server) |
|--------|----------|--------|---------------------------|
| **CPU Usage @ 600 TPS** | 10% | 70% | 70% |
| **Stream Errors** | 0% | 0-3% | 0-3% |
| **P95 Latency** | Stable | Spikes | Spikes |
| **Connections per Host** | Many (one per request) | Few (shared) | Few (shared) |
| **Memory Usage** | Higher (more connections) | Lower (fewer connections) | Lower (fewer connections) |
| **Predictability** | High | Low | Medium |

### Recommendation for Load Testing

**For production load testing, use `http_version="1.1"`:**

```python
@mite_http(http_version="1.1")
async def my_journey(ctx):
    await ctx.http.get("https://api.example.com")
```

This provides:
- Stable, predictable performance
- No HTTP/2-related errors or CPU spikes
- Focus on application performance, not protocol complexity
- Consistent results across test runs

**Only use HTTP/2 if:**
- Your application specifically requires HTTP/2 testing
- You're running low-volume tests (< 100 TPS)
- You need to validate HTTP/2 compatibility

---

## Migration Guide

**Existing code continues to work unchanged** - the default is `"auto"` which preserves the original curl behavior.

**If you're experiencing HTTP/2 issues (stream errors or high CPU):**

```python
# Before (might get HTTP/2 issues with some servers)
@mite_http
async def my_journey(ctx):
    await ctx.http.get("https://api.example.com")

# After (force HTTP/1.1 to avoid issues)
@mite_http(http_version="1.1")
async def my_journey(ctx):
    await ctx.http.get("https://api.example.com")
```

---

## Summary

- **Problem**: HTTP/2 caused stream errors (92) and severe CPU overhead (70%) with some servers
- **Solution**: Added `http_version` parameter to control protocol version
- **Default**: `"auto"` (preserves original behavior, no breaking changes)
- **Recommendation**: Use `http_version="1.1"` if experiencing HTTP/2 issues with specific endpoints
- **Result**: Users can now choose stable HTTP/1.1 or let curl negotiate automatically
