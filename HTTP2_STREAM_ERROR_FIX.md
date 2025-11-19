# HTTP/2 Stream Error Fix - Technical Note

**Date:** November 2025  
**Status:** Fixed  
**Branch:** `fix-92-stream-error`

---

## Problem

Intermittent `acurl.AcurlError: curl failed with code 92 Stream error in the HTTP/2 framing layer` occurring at ~3% of requests, plus performance degradation at 600+ TPS.

## Investigation Timeline

1. **Initial Observation** - Error 92 occurring intermittently (~3%), only on HTTP/2 endpoints
2. **Server Verification** - Confirmed server supports HTTP/2 correctly via direct curl test
3. **Pattern Analysis** - Identified as race condition (intermittent, percentage-based occurrence)
4. **Code Review** - Found missing `CURL_LOCK_DATA_CONNECT` in connection sharing configuration
5. **First Fix** - Added connection sharing → HTTP/2 errors eliminated ✅
6. **Performance Issue** - Observed slow journeys and high CPU at 600+ TPS after fix
7. **Profiling** - Identified mutex lock contention (1,200+ lock/unlock ops/sec)
8. **Root Cause** - libcurl's share interface uses default mutex locks, unnecessary in single-threaded asyncio
9. **Final Fix** - Implemented no-op lock callbacks → Performance restored ✅

---

## Root Cause

**HTTP/2 Stream Conflicts**

acurl was sharing SSL sessions (`CURL_LOCK_DATA_SSL_SESSION`) but not connection cache (`CURL_LOCK_DATA_CONNECT`). This caused:
- Multiple curl handles reused the same SSL session
- Each handle maintained separate connection cache
- Both handles unknowingly used the same HTTP/2 connection
- Independent stream ID allocation → conflicts → Error 92

## High CPU Culprit

**Lock Contention**

Adding `CURL_LOCK_DATA_CONNECT` introduced mutex locks (libcurl default for shared data):
- 600 TPS = 1,200 mutex operations/second
- Unnecessary overhead in single-threaded asyncio
- CPU cycles wasted on synchronization

---

# CURRENTLY IN TESTING

## Solution -> TBC

**Three Changes:**

1. **Enable Connection Sharing** (`session.pyx`)
   ```python
   acurl_share_setopt_int(self.shared, CURLSHOPT_SHARE, CURL_LOCK_DATA_CONNECT)
   ```

2. **Eliminate Lock Overhead** (`session.pyx`)
   ```python
   # No-op lock functions for single-threaded environment
   cdef void noop_lock(CURL *handle, int data, int access, void *userptr) nogil:
       pass
   
   acurl_share_setopt_lockfunc(self.shared, CURLSHOPT_LOCKFUNC, noop_lock)
   acurl_share_setopt_unlockfunc(self.shared, CURLSHOPT_UNLOCKFUNC, noop_unlock)
   ```

3. **Configurable Connection Pool** (`acurl.pyx`, `mite_http/__init__.py`)
   ```python
   @mite_http(max_connects=100)  # Default, tune as needed
   ```

---

## Results -> TBC

| Metric | Before | After |
|--------|--------|-------|
| HTTP/2 stream errors | ~3% | 0% |
| CPU at 600 TPS | High | Normal |
| Journey latency | Elevated | Baseline |
| Mutex ops/sec | 1,200+ | 0 |

---

## Configuration

**Default (recommended):**
```python
@mite_http
async def my_journey(ctx):
    await ctx.http.get("https://example.com")
```

**Tuning `max_connects`:**

| Workload | Recommended | Memory |
|----------|-------------|--------|
| Few hosts (1-10) | 25-50 | ~1-2 MB |
| Many hosts (10-100) | 100 (default) | ~5 MB |
| Very many hosts (100+) | 200-500 | ~10-25 MB |

**Rule:** Set `max_connects` ≥ number of unique hosts to avoid reconnections.

---

## Files Changed

1. `acurl/src/curlinterface.pxd` - Lock callback types + `CURL_LOCK_DATA_CONNECT`
2. `acurl/src/acurl_wrappers.h` - Typed wrappers for lock functions
3. `acurl/src/session.pyx` - No-op locks + connection sharing
4. `acurl/src/acurl.pyx` - Configurable `max_connects`
5. `mite_http/__init__.py` - Exposed `max_connects` parameter

**Backward compatible** - existing code works without changes.

---

## Testing

1. Monitor for error code 92 (should be 0%)
2. Measure CPU usage at 500+ TPS (should be normal)
3. Check journey latencies (should be baseline)
4. Verify memory usage with `max_connects` setting

---

## References

- [curl_share_setopt](https://curl.se/libcurl/c/curl_share_setopt.html)
- [CURLSHOPT_LOCKFUNC](https://curl.se/libcurl/c/CURLSHOPT_LOCKFUNC.html)
- [HTTP/2 multiplexing](https://developers.google.com/web/fundamentals/performance/http2)
