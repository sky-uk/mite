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
- Minimum Python raised to 3.11 (`aio_pika` requires it).
- `http` extra bumped to `httpperf==1.0rc10`, which ships prebuilt wheels
  for macOS in addition to Linux.

### Added

- `nanomsg` extra (previously a core dependency).
- CI check that a core-only install still works
  (`cd-scripts/checkCoreInstall.sh`).

### Removed

- The `FutureWarning`s added in 2.12.0 announcing this release.

### Migration

Change `mite` to `mite[all]` in your requirements to keep every integration.
See also the stats pipeline migration below.

### Stats pipeline

Breaking: one aggregation pipeline for every run mode, with any number of
stats outputs.

#### Changed

- **Stats outputs are URLs.** `--stats-output=URL`, repeated once per output,
  replaces `--influxdb=N`, `--include-buckets` and `--web-address`, on
  `mite scenario test`, `mite journey test` and the new `mite exporter`:
  - `prometheus://[HOST][:PORT]` (default `127.0.0.1:9301`)
  - `influxdb1://HOST[:PORT]/DATABASE[/RETENTION_POLICY]`
  - `influxdb2://HOST[:PORT]/ORG/BUCKET`
  - `influxdb3://HOST[:PORT]/DATABASE`
  - query parameters `tls=true`, `buckets=true`, `token_env` (v2, v3),
    `username_env` / `password_env` (v1)

  Credentials are read from environment variables named by the `*_env`
  parameters (defaults `INFLUXDB_TOKEN`, `INFLUXDB_USERNAME`,
  `INFLUXDB_PASSWORD`). A URL containing credentials is rejected, with them
  masked in the error. `INFLUXDB_HOST`, `_VERSION`, `_DATABASE`, `_BUCKET`,
  `_ORG`, `_RETENTION_POLICY`, `_INCLUDE_BUCKETS` and their `_2`, `_3`, ...
  forms are no longer read.
- **`mite exporter`** replaces `mite prometheus_exporter` and
  `mite influxdb_exporter`; choose its outputs with `--stats-output`.
- **`mite influxdb init URL...`** takes the same URLs as `--stats-output`,
  replacing `--influxdb=N`.
- **Stat definitions are immutable.** `Counter`, `Accumulator`, `Gauge` and
  `Histogram` keep their constructor arguments, so plugins that build stats
  with them need no changes. The running values move to `StatAggregation`
  objects (`CounterAggregation`, ...) that each aggregator creates, so
  `process()`, `dump()`, `metrics`, `bin_counts`, `sums` and `total_counts`
  are no longer on the definitions. `Histogram.bins` is a sorted tuple.
- **`mite.stats.Stats` is now `Aggregator`**, and takes a list of senders
  (anything with `send(dump)` and `close()`) instead of a `sender` callable:
  `Aggregator([sender])`. `flush()` sends a dump to every sender; `close()`
  sends what's left and closes them.
- **`mite ... test` runs one aggregator** for all outputs, instead of one per
  InfluxDB instance.
- Prometheus prints counters as integers throughout (a label combination
  first seen after the first dump used to print as `1.0`).
- A bad `--stats-output` is reported as a one-line `mite: ...` error.

#### Added

- `mite_stats_outputs` entry point group, so plugins can add stats outputs
  for a URL scheme.
- Custom stat types: subclass `Stat` and `StatAggregation` (see
  `docs/stats.rst`).
- Several `prometheus://` outputs in one process, on different ports.

#### Removed

- `mite.influxdb_processor.InfluxDBProcessor`, `mite.web` (now
  `mite.stats_outputs`), `mite.web.influx_metrics`, and the `packaging`
  dependency.

#### Fixed

- With `--influxdb=2` (now two InfluxDB `--stats-output`s), every message was
  counted twice and one output's dump cleared the other's counts, because all
  aggregators shared the plugins' stat objects (first reported, and a fix
  proposed, by Davide Annunziata).
- Stats gathered since the last dump were lost at the end of a test run, and
  when `mite stats` or `mite exporter` stopped.
- `mite stats` and `mite exporter` now exit cleanly on SIGINT and SIGTERM,
  sending their final dump. Before, they hung on SIGINT and lost the final
  dump on SIGTERM, which Kubernetes sends.
- `mite influxdb init` includes custom stat types, and a stat with an
  unknown dump type is skipped with an error instead of crashing the output.

#### Migration

| Before | After |
|---|---|
| `mite prometheus_exporter --web-address=0.0.0.0:9301` | `mite exporter --stats-output=prometheus://0.0.0.0:9301` |
| `mite influxdb_exporter` with `INFLUXDB_*` | `mite exporter --stats-output=influxdb3://HOST:PORT/DATABASE` (or `influxdb1://`, `influxdb2://`) |
| `--influxdb=2` with `INFLUXDB_*` and `INFLUXDB_*_2` | one `--stats-output` per server, e.g. `...?token_env=INFLUXDB_TOKEN_2` for the second |
| `--include-buckets` | `?buckets=true` on the InfluxDB URL |
| `mite influxdb init --influxdb=2` | `mite influxdb init URL URL` |
| `Stats(sender=s.send)` | `Aggregator([s])` |
| `stat.process(msg)` / `stat.dump()` | `a = stat.aggregation_class(stat)`, then `a.process(msg)` / `a.dump()` |

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
