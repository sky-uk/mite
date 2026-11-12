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

## Connection settings

Each `@mite_http` journey gets its own acurl `Session`, and every journey in a
runner shares one acurl `Engine`. Both are configured through mite config, so set
them with `MITE_CONF_` environment variables, for example
`MITE_CONF_http_version=HTTP/1.1`. See the
[acurl connections guide](https://github.com/tonysimpson/acurl/blob/main/docs/connections.md)
for what each option does.

Engine options are read once, when a runner makes its first request:

| Config key | Default | acurl `Engine` argument |
|---|---|---|
| `http_max_host_connections` | `0` (no limit) | `max_host_connections` |
| `http_max_total_connections` | `0` (no limit) | `max_total_connections` |
| `http_max_idle_connections` | `1000` | `max_idle_connections` |

Session options are read at the start of each journey, so changes apply to the
next journeys:

| Config key | Default | acurl `Session` argument |
|---|---|---|
| `http_connections` | `shared` | `connections` (`shared`, `session` or `none`) |
| `http_tls` | `session` | `tls` (`shared` or `session`) |
| `http_version` | `HTTP/2` | `http_version` (`HTTP/1.1`, `HTTP/2` or `HTTP/3`) |
| `http_idle_timeout` | `118` | `idle_timeout` (seconds) |
| `http_max_connection_age` | `0` (no limit) | `max_connection_age` (seconds) |
| `http_session_max_host_connections` | `0` (no limit) | `max_host_connections` |
| `http_session_max_connections` | `0` (no limit) | `max_connections` |
| `http_timeout` | none | `timeout` (seconds) |
| `http_connect_timeout` | curl's default | `connect_timeout` (seconds) |
| `http_verify` | `false` | `verify` (`true`, `false` or a CA bundle path) |

The defaults keep the connection behaviour of mite's old acurl fork (one shared
pool, TLS session tickets per journey). HTTP/2 is negotiated over https where the
server offers it, falling back to HTTP/1.1, as before; the difference is that
requests to an HTTP/2 server now wait to share one connection (curl's
`PIPEWAIT`) rather than each opening their own. `HTTP/3` has no fallback and
needs a libcurl built with HTTP/3 support. The session is closed when the journey
ends, including when it raises.

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
