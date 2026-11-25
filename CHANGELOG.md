# Changelog

## [Unreleased]

### Added

- `mite_http.checks`: `check_status_code`, `check_status_code_in_groups`,
  `is_error_status_code` and `UnexpectedResponseCodeError`. Checks raise
  `MiteError` (no `assert`) and take an optional `on_failure` hook.
- `mite_browser.Browser.put`, `.delete` and `.head`.

### Fixed

- `har_to_mite` output now runs as-is: it imports checks from
  `mite_http.checks` instead of a missing `.utils`, supports
  PUT/DELETE/HEAD, replays recorded bodies byte-for-byte, escapes URLs and
  headers, and drops `Content-Length` and HTTP/2 pseudo-headers. A recorded
  304 now expects exactly 200 or 304.
- `har_to_mite` paces requests with `ensure_fixed_separation` instead of
  `sleep`. The recorded gap now applies after the request it belongs to
  (it was one request late), keeps millisecond precision, and includes the
  response time. `mite har --sleep-time=0` now uses the recorded gaps; the
  value used to stay a string and never matched 0.
- `har_to_mite` no longer drops the request that follows a collapsed
  redirect.

## 3.0.0

### Breaking changes
- **HTTP client replaced.** mite's vendored Cython fork of acurl (published as
  `acurl` ≤ 1.2.1) is removed. `mite_http` now uses
  [httpperf](https://github.com/tonysimpson/httpperf) (`httpperf==1.0rc10`),
  which runs libcurl on its own thread. Response timings are no longer inflated
  when the runner's event loop is busy.
- **`method` label** on `mite_http_response_total` is now `GET` (was `b'GET'`).
- **`start_time`** in `http_metrics` is a float (was whole seconds);
  `download_size` is an int (was a float).
- **Errors** are `httpperf.RequestError` (`httpperf.Timeout` for timeouts), with
  curl's detailed messages. `mite_http.AcurlError` remains as an alias.
- **Response headers** (`resp.headers`) are read-only and decoded as latin-1;
  `resp.text` of JSON responses without a charset is decoded as UTF-8.
- References to "mite 3.0" in deprecation warnings and docs now say mite 4.0.

### Compatibility kept (`mite_http/compat.py`)
Journeys written for the old fork work unchanged:
- `cert=(key, cert)` order, header lists of pairs, and `Cookie` objects in
  `cookies=` are translated.
- `str`/`bytes` `data=` still gets `Content-Type: application/x-www-form-urlencoded`
  unless one is set.
- `json=` bodies are byte-for-byte the same as before (encoded with ujson).
- `head()` follows redirects by default.
- `resp.cookies` is the session's cookie jar; `resp.request.to_curl()` and
  `mite_http.to_curl(resp)` reproduce a request, including jar cookies.
- `create_http_cookie(ctx, domain, name, value)` builds an `httpperf.Cookie`.

### Added
- **Connection settings** through mite config (`MITE_CONF_http_*`): connection
  pooling (`http_connections`), TLS session reuse (`http_tls`), HTTP version
  (default HTTP/2 with fallback to HTTP/1.1), connection limits, idle/age
  timeouts, request and connect timeouts, and `http_verify`. Defaults match
  the old fork's behaviour. See `docs/plugins/http.md`.
- **New `http_metrics` fields:** `upload_size`, `queue_time`, `client_lag`,
  `posttransfer_time`, `http_version`.
- **`mite_http_extended` stats processor** (opt-in): histograms for DNS,
  connect, TLS, pre/post-transfer and first-byte times, connection queue time,
  client lag, and download/upload sizes. Off by default; enable by naming it
  in `--stats-include-processors`.
- **Opt-in stats processors:** processors listed in
  `mite.stats.DEFAULT_EXCLUDED_PROCESSORS` load only when named in
  `--stats-include-processors`.
- **OpenTelemetry HTTP spans** now work in traced journeys (previously the
  patch silently failed). Spans cover `request()` too and include TLS,
  pre/post-transfer, queue and client-lag timings, body sizes, protocol
  version and peer address. Trace headers are injected into a copy of the
  caller's headers.

### Fixed
- The `mite_http` session is closed when a journey raises.
- Non-UTF-8 response headers no longer raise `UnicodeDecodeError`, and reading
  `redirect_url` on a non-redirect no longer crashes.
- `mite_browser`'s `erase_session_cookies()` and `get_cookie_list()` now work.

### Removed
- The `acurl/` package, its build, test and release jobs (`acurl-ci`, wheel
  builds, PyPI version check), Cython, and `cd-scripts/cdBuild-old.sh`.
- `mite_dns_time` (never registered); replaced by
  `mite_http_dns_time_seconds` in `mite_http_extended`.
