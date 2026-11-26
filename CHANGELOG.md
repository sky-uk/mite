# Changelog

All notable changes to this project are documented here. Format is loosely
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

<!--
Working section for the mite-v4-major-release merge. Entries are grouped
by source branch, in merge order, so a later branch's revert of an earlier
branch's change is visible instead of silently landing twice. Before
tagging 4.0.0: walk the branches in order, drop any entry that a later
branch undoes, flatten what's left into the standard Breaking
changes/Added/Changed/Fixed/Removed sections (see the 3.0.0 entry below
for the target shape), and delete the branch headings and this comment.
-->

#### feature/packaging-4.0.0

<!-- merged: feature/packaging-4.0.0 -->

##### Breaking changes

- **Core-only install.** `pip install mite` now installs only the core
  framework. Integrations must be installed via their extra (`http`,
  `kafka`, `amqp`, `websocket`, `finagle`, `selenium`, `selenium_wire`,
  `s3`, `db`, `browser`). See `pyproject.toml` for exact versions.
  `pip install 'mite[all]'` reproduces the old default install.
- **`otel` extra** now also includes `mite[http]`.
- **Minimum Python raised to 3.11** (`aio_pika` requires it).
- **`http` extra bumped to `httpperf==1.0rc10`**, which ships prebuilt
  wheels for macOS in addition to Linux.

##### Added

- `nanomsg` extra (previously a core dependency).
- CI check that a core-only install still works
  (`cd-scripts/checkCoreInstall.sh`).

##### Removed

- The `FutureWarning`s added in 2.12.0 announcing this release.

##### Migration

Change `mite` to `mite[all]` in your requirements to keep every integration.
No other changes needed.

#### stats-isolation-fix

<!-- merged: stats-isolation-fix -->

##### Fixed

- Each `Stats()` instance now deep-copies its stat objects instead of
  sharing the module-level `STATS` lists. Running more than one instance
  (e.g. `--influxdb=2`) double-counted messages and let one instance's
  `dump()` clear another's pending data.

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

### Known issue, fixed in 3.0.0

Added `aio_pika>=10.0`, which requires Python 3.11+, without noticing
`requires-python` still advertised 3.10 support. `pip install mite` was
unsatisfiable on 3.10 from here through 2.12.0.
