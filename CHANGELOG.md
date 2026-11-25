# Changelog

All notable changes to this project are documented here. Format is loosely
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

Breaking: dependency slimming, part 2 of 2.

### Changed

- `pip install mite` now installs only the core framework. Integrations
  must be installed via their extra (`http`, `kafka`, `amqp`, `websocket`,
  `finagle`, `selenium`, `selenium_wire`, `s3`, `db`, `browser`) — see
  `pyproject.toml` for exact versions. `pip install 'mite[all]'` reproduces
  the old default install.
- `otel` extra now also includes `mite[http]`.
- `amqp` extra requires Python 3.11+ (`aio_pika>=10.0` doesn't support
  3.10). Core and every other extra still support Python 3.10.
- `http` extra bumped to `httpperf==1.0rc10`, which ships prebuilt wheels
  for macOS in addition to Linux.

### Added

- `nanomsg` extra (previously a core dependency).
- CI check that a core-only install still works
  (`cd-scripts/checkCoreInstall.sh`).
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

### Removed

- The `FutureWarning`s added in 2.12.0 announcing this release.

### Migration

Change `mite` to `mite[all]` in your requirements to keep every integration.
No other changes needed.

## 3.0.0

### Breaking changes
- **HTTP client replaced.** mite's vendored Cython fork of acurl (published as
  `acurl` ≤ 1.2.1) is removed. `mite_http` now uses
  [httpperf](https://github.com/tonysimpson/httpperf) (`httpperf==1.0rc8`),
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

## [2.12.0] - 2026-10-27

Non-breaking prep for the dependency slim above.

### Added

- Install extras for every optional integration (no-ops until 4.0.0).
- `FutureWarning`s announcing which extra each integration will need.
- Missing `mite_playwright` stats entry point.

### Changed

- Heavy third-party imports deferred to first use instead of module load.
- `packaging` declared as a direct dependency.

### Fixed

- Dockerfile zlib version bumped (security).

## [2.11.0] - 2026-10-19

### Added

- InfluxDB exporter.

### Changed

- Release pipeline hardened: pinned toolchain, credentials no longer
  written to disk, fixed a duplicate tag-push.

## [2.10.0] - 2026-09-21

### Changed

- Migrated to Python 3.12 and `uv` for the dev/CI environment.

### Known issue, fixed in 4.0.0

Added `aio_pika>=10.0`, which requires Python 3.11+, without noticing
`requires-python` still advertised 3.10 support. `pip install mite` was
unsatisfiable on 3.10 from here through 3.0.1; fixed in 4.0.0 by moving
`aio_pika` into the `amqp` extra with a `python_version >= '3.11'` marker,
so core and every other extra still support 3.10.
