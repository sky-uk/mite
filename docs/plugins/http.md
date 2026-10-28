# HTTP

`mite_http` is mite's HTTP integration. It installs an async HTTP client onto
the journey context, built on top of {doc}`acurl <acurl>`, and automatically
reports timing metrics for every request.

Install: `pip install mite[http]` (no functional change today — every mite
install already includes it; this will matter starting in mite 3.0).

## Basic usage

```python
from mite_http import mite_http

@mite_http
async def journey(ctx):
    async with ctx.transaction("Get homepage"):
        response = await ctx.http.get("https://example.com")
```

The `@mite_http` decorator installs `ctx.http`, an HTTP session, for the
duration of the journey call. Naming the transaction matters: the transaction
name becomes the `transaction` label on every metric the request produces, so
`mite_http_response_time_seconds{transaction="Get homepage"}` is how you'd find
this request's latency later.

## Making requests

`ctx.http` exposes one async method per HTTP verb:

```python
await ctx.http.get(url, ...)
await ctx.http.post(url, ...)
await ctx.http.put(url, ...)
await ctx.http.patch(url, ...)
await ctx.http.delete(url, ...)
await ctx.http.head(url, ...)
await ctx.http.options(url, ...)
```

All of them accept the same keyword arguments:

| Keyword | Meaning |
|---|---|
| `headers` | a mapping of request headers |
| `cookies` | a mapping of cookies to send with the request |
| `auth` | basic auth credentials |
| `data` | a request body, `str` or `bytes` |
| `json` | a JSON-serializable object; mutually exclusive with `data`, and sets `Content-Type: application/json` automatically |
| `cert` | client certificate |
| `allow_redirects` | follow redirects automatically (default `True`) |
| `max_redirects` | redirect limit before raising (default `5`) |

```python
await ctx.http.post(
    "https://example.com/users",
    json={"username": "test"},
    headers={"Authorization": "Bearer token"},
)
```

## The response

Each call returns a response object with:

- `status_code`
- `text` — decoded body
- `json()` — body parsed as JSON
- `body` — raw bytes
- `headers`
- `cookies`
- `encoding`
- `url` — the final URL after any redirects
- `history` — the chain of responses that preceded a redirect

## Metrics emitted

Every request sends an `http_metrics` message, which is what the registered
stats processors (below) turn into Prometheus series:

| Field | Meaning |
|---|---|
| `start_time` | when the request started |
| `effective_url` | the URL actually requested |
| `response_code` | HTTP status code |
| `dns_time` | DNS resolution time |
| `connect_time` | TCP connect time |
| `tls_time` | TLS handshake time |
| `transfer_start_time` | time to start of transfer |
| `first_byte_time` | time to first response byte |
| `total_time` | total request duration |
| `primary_ip` | resolved IP the request went to |
| `method` | HTTP method used |
| `download_size` | bytes downloaded |

## Stats and tuning

`mite_http` registers two processors under `mite_stats`, listed in full on
{doc}`../stats`:

- `mite_http_response_total` — a counter, labelled by `test`, `journey`,
  `transaction`, `method` and `response_code`
- `mite_http_response_time_seconds` — a histogram of `total_time`, labelled by
  `transaction`

The histogram's bucket boundaries can be overridden with the
`MITE_HTTP_HISTOGRAM_BUCKETS` environment variable, a comma-separated list of
floats (seconds):

```bash
export MITE_HTTP_HISTOGRAM_BUCKETS=0.01,0.05,0.1,0.5,1,5
```

The default buckets run from 100 microseconds to 64 seconds.

## Custom metrics per request

Anything set on `ctx.http.additional_metrics` is merged into the next
`http_metrics` message:

```python
ctx.http.additional_metrics = {"cache_status": "miss"}
await ctx.http.get(url)
```

For more control, `ctx.http.set_response_callback(cb)` registers a callback
invoked with every response: `cb(response, additional_metrics)`, where
`additional_metrics` is the same dict described above, so the callback can
inspect the response before deciding what to add.

## Cookies

`create_http_cookie(ctx, *args, **kwargs)` builds a cookie object to populate
the `cookies` argument above. Session-wide cookies can be cleared with
`ctx.http.erase_all_cookies()`.

## See also

- {doc}`acurl <acurl>` — the libcurl wrapper `mite_http` is built on
- {doc}`../otel` — `mite_http_traced`, a drop-in replacement for `@mite_http`
  that additionally creates OpenTelemetry spans
- {doc}`../stats` — the full list of registered stats processors
