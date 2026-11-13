# HTTP

`mite_http` is mite's HTTP integration. It installs an async HTTP client onto
the journey context, built on top of {doc}`httpperf <httpperf>`, and automatically
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
| `data` | a request body, `str` or `bytes`, sent with `Content-Type: application/x-www-form-urlencoded` unless you set a `Content-Type` (as earlier versions of mite did); or a dict, which is form-encoded |
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

JSON is encoded and decoded with [ujson](https://github.com/ultrajson/ultrajson).
`json=` bodies are formatted exactly as the standard library's `json.dumps`
does by default (`{"username": "test"}`, with spaces after `,` and `:`, and
non-ASCII characters escaped), so they match what earlier versions of mite sent.

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
| `start_time` | when the request started (wall clock, seconds as a float) |
| `effective_url` | the URL actually requested |
| `response_code` | HTTP status code |
| `dns_time` | curl: DNS lookup complete, from the start of the transfer |
| `connect_time` | curl: TCP connect complete, from the start of the transfer; 0 when a connection was reused |
| `tls_time` | curl: TLS handshake complete, from the start of the transfer; 0 for plain http and reused connections |
| `transfer_start_time` | curl: ready to send the request (curl's `pretransfer_time`), from the start of the transfer |
| `first_byte_time` | curl: first response byte received (curl's `starttransfer_time`), from the start of the transfer |
| `total_time` | curl: transfer complete, from the start of the transfer |
| `primary_ip` | resolved IP the request went to |
| `method` | HTTP method used, e.g. `GET` |
| `download_size` | bytes downloaded |
| `upload_size` | bytes uploaded |
| `queue_time` | time waiting in httpperf's queue for a connection, under the connection limits; not part of the other timings |
| `client_lag` | time the request spent waiting on Python (before it was sent and after it finished); if this grows, the runner is the bottleneck |
| `posttransfer_time` | curl: request fully sent, from the start of the transfer; `None` with libcurl older than 8.10 |
| `http_version` | protocol negotiated: `HTTP/1.1`, `HTTP/2` or `HTTP/3` |

## Stats and tuning

`mite_http` registers two stats processors under `mite_stats` (see
{doc}`../stats`).

### `mite_http` (on by default)

| Stat | Type | Labels | What it shows |
|---|---|---|---|
| `mite_http_response_total` | counter | `test`, `journey`, `transaction`, `method`, `response_code` | Number of responses. Use it for request rates and error rates by status code. |
| `mite_http_response_time_seconds` | histogram | `transaction` | `total_time`: curl's time for the whole transfer, from the start of the request (DNS, connect and TLS included when a new connection is made) to the last byte of the response. This is the response time a client sees, apart from any time spent queueing in httpperf or waiting on Python. |

### `mite_http_extended` (opt-in)

Everything curl and httpperf measure beyond the overall response time, broken down
so you can see where the time goes. They are off by default, because each adds a
histogram series per transaction. Turn them on with
`--stats-extra-processors=mite_http_extended`, on `mite stats` or on
`mite scenario test`/`mite journey test` when used with `--influxdb`.

All are histograms labelled by `transaction`: timings in seconds, sizes in bytes.

**curl's timings.** Like `total_time`, each is measured from the start of the
transfer, so they add up: DNS ≤ connect ≤ TLS ≤ pretransfer ≤ posttransfer ≤ first
byte ≤ total. Subtract neighbouring values to get the length of one phase.

```
start → DNS done → TCP connected → TLS done → ready to send → request sent → first byte → done
        dns_time   connect_time    tls_time   pretransfer     posttransfer   first_byte   total_time
```

| Stat | What it shows |
|---|---|
| `mite_http_dns_time_seconds` | `dns_time`: time to resolve the host name. Usually near zero once the name is cached; large values point at DNS problems on the load generator's side. |
| `mite_http_connect_time_seconds` | `connect_time`: time to establish the TCP connection (including DNS). **Only requests that opened a new connection are recorded**; reused connections report 0 and are skipped, so this shows the cost of new connections, and its count shows how many were opened. Growth means slow accepts at the server or load balancer, or network latency. |
| `mite_http_tls_time_seconds` | `tls_time`: time until the TLS handshake finished (including DNS and connect). Only new https connections are recorded. The gap above `connect_time` is the handshake itself; it is larger for full handshakes than for resumed ones (see `http_tls` under [Connection settings](#connection-settings)). |
| `mite_http_pretransfer_time_seconds` | `transfer_start_time`: time until curl was ready to send the request, i.e. all connection setup done. For a reused connection this is close to zero. |
| `mite_http_posttransfer_time_seconds` | `posttransfer_time`: time until the request, including any body, was fully sent. The gap above pretransfer is upload time. Not recorded when libcurl is older than 8.10. |
| `mite_http_first_byte_time_seconds` | `first_byte_time`: time until the first byte of the response arrived. This is time to first byte as a client sees it, including connection setup and upload. On a reused connection with no request body, it is close to the server's processing time plus one round trip; `first_byte_time - posttransfer_time` gives that for every request. |

**Measured by httpperf, outside curl's timings.** Neither is included in
`total_time` or in the timings above.

| Stat | What it shows |
|---|---|
| `mite_http_queue_time_seconds` | `queue_time`: how long a request waited in httpperf for a free connection, because of the `http_*max*connections` limits (see [Connection settings](#connection-settings)). Normally zero; if it grows, the connection limits, not the server, are holding requests back. |
| `mite_http_client_lag_seconds` | `client_lag`: time the request spent waiting on Python, before it was handed to curl and after the response arrived. It measures the load generator, not the service. If it grows, the runner can't keep up (CPU-bound journeys, too many runners per core), so achieved request rates describe the client rather than the server. Report it alongside response times. |

**Sizes**, in bytes. Their buckets are set separately with
`MITE_HTTP_SIZE_HISTOGRAM_BUCKETS` (default 128 B to 64 MiB, in powers of 4).

| Stat | What it shows |
|---|---|
| `mite_http_download_size_bytes` | `download_size`: bytes of response body received, as reported by curl (headers excluded). Includes empty responses such as `HEAD` and `204`. Useful for spotting responses that are bigger than expected, which drive bandwidth and transfer time. |
| `mite_http_upload_size_bytes` | `upload_size`: bytes of request body sent. **Only requests with a body are recorded**; requests that upload nothing (most `GET`s) are skipped. |

The histograms' bucket boundaries can be overridden with the
`MITE_HTTP_HISTOGRAM_BUCKETS` environment variable, a comma-separated list of
floats (seconds):

```bash
export MITE_HTTP_HISTOGRAM_BUCKETS=0.01,0.05,0.1,0.5,1,5
```

The default buckets run from 100 microseconds to 64 seconds.

## Connection settings

Each `@mite_http` journey gets its own httpperf `Session`, and every journey in a
runner shares one httpperf `Engine`. Both are configured through mite config, so set
them with `MITE_CONF_` environment variables, for example
`MITE_CONF_http_version=HTTP/1.1`. See the
[httpperf connections guide](https://github.com/tonysimpson/httpperf/blob/main/docs/connections.md)
for what each option does.

Engine options are read once, when a runner makes its first request:

| Config key | Default | httpperf `Engine` argument |
|---|---|---|
| `http_max_host_connections` | `0` (no limit) | `max_host_connections` |
| `http_max_total_connections` | `0` (no limit) | `max_total_connections` |
| `http_max_idle_connections` | `1000` | `max_idle_connections` |

Session options are read at the start of each journey, so changes apply to the
next journeys:

| Config key | Default | httpperf `Session` argument |
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

## Reproducing a request with curl

`resp.request.to_curl()` returns a curl command line that repeats the request:
method, URL, headers, body, basic auth, and the cookies that would have been
sent (those passed to the request plus those in the journey's cookie jar for the
URL). `mite_http.to_curl(resp)` does the same.

```python
logger.info("Reproduce with: %s", resp.request.to_curl())
```

The cookie jar is read when you call it, so call it while the journey is
running, for example in a response callback. After the journey has ended only
the request's own cookies are included.

Responses from `ctx.http` (and those passed to response callbacks) are thin
wrappers around httpperf's `Response` that add this method and keep `cookies`
as the whole jar (see [Cookies](#cookies)); every other attribute is
httpperf's own.

## Cookies

Each journey gets a new httpperf session with an empty cookie jar, which is
discarded when the journey ends (whether or not it raised). Cookies set by the
server, and cookies you pass to requests, stay in the jar for the rest of the
journey.

Sending cookies:

- `cookies={"name": "value"}` on any request adds them to the jar as session
  cookies for the request's host and its subdomains, path `/`.
- `cookie_list=[...]` adds `httpperf.Cookie` objects, for control over domain,
  path, expiry and flags. `create_http_cookie(ctx, domain, name, value)` builds
  one with the same defaults as `cookies=`:

  ```python
  cookie = create_http_cookie(ctx, ".example.com", "session", "abc")
  await ctx.http.get(url, cookie_list=[cookie])
  ```

  `Cookie` objects passed as values in `cookies={...}` are also accepted, and
  moved to `cookie_list` for you.

Reading and changing the jar:

| Call | Returns or does |
|---|---|
| `ctx.http.cookies()` | the jar as a `{name: value}` dict |
| `ctx.http.get_cookie_list()` | the jar as `httpperf.Cookie` objects (domain, path, expiry, flags) |
| `ctx.http.add_cookie_list(cookies)` | adds `Cookie` objects to the jar |
| `ctx.http.erase_all_cookies()` | empties the jar |
| `ctx.http.erase_session_cookies()` | removes cookies without an expiry, as a browser restart would |
| `resp.cookies` | the **whole jar** at the time you read it, as a dict, not only the cookies that response set (as in earlier versions of mite). Empty once the journey has ended. |
| `resp.cookielist` | only the cookies **that response set**, from its `Set-Cookie` headers, as `Cookie` objects |
| `resp.request.cookie_list` | only the cookies passed to that request |

`get_cookie_list()`, `resp.cookielist` and `cookie_list=` all use
`httpperf.Cookie`, so cookies read from one place can be passed straight to another.
In the dict forms, cookies with the same name on different domains overwrite
each other.

## See also

- {doc}`httpperf <httpperf>` — the libcurl wrapper `mite_http` is built on
- {doc}`../otel` — `mite_http_traced`, a drop-in replacement for `@mite_http`
  that additionally creates OpenTelemetry spans
- {doc}`../stats` — the full list of registered stats processors
