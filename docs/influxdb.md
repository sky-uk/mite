# InfluxDB

Mite can write live test metrics (counters, gauges, histograms) to InfluxDB
v1, v2, or v3, either as part of an in-process test run or as a standalone
exporter process consuming stats from the message bus.

It converts the internal stats model (`Counter`, `Gauge`, `Histogram` — see
[mite/stats.py](https://github.com/sky-uk/mite/blob/master/mite/stats.py)) into
InfluxDB line-protocol points and writes them to one or more InfluxDB instances.

## Quick start

### Configuration

Set `INFLUXDB_VERSION` to select the client (default `v3`), then the
matching variables below. Each InfluxDB instance you write to is named in
`--stats-output=influxdb:INSTANCE`, and its variables carry that name in upper
case as a suffix: `influxdb:secondary` reads `INFLUXDB_HOST_SECONDARY` and so
on, `influxdb:2` reads `INFLUXDB_HOST_2`. Plain `influxdb` reads the
unsuffixed variables.

| Version | Required env vars |
|---|---|
| v1 | `INFLUXDB_HOST`, `INFLUXDB_USERNAME`, `INFLUXDB_PASSWORD`, `INFLUXDB_DATABASE` (optional `INFLUXDB_RETENTION_POLICY`, default `autogen`) |
| v2 | `INFLUXDB_HOST`, `INFLUXDB_TOKEN`, `INFLUXDB_BUCKET`, `INFLUXDB_ORG` |
| v3 | `INFLUXDB_HOST`, `INFLUXDB_TOKEN`, `INFLUXDB_DATABASE` |

Set `INFLUXDB_INCLUDE_BUCKETS{suffix}=true` to also write raw histogram bucket
points (`le`-tagged, Prometheus-style) alongside the computed percentiles, so
downstream tools can reconstruct exact distributions.

A fuller reference, including how each version maps onto the underlying
client, is in [Configuration reference](#configuration-reference) below.

### Via `mite` test run (in-process)

Pass `--stats-output=influxdb[:INSTANCE]` once per InfluxDB instance:

```bash
# Default instance (INFLUXDB_* variables)
mite journey test --stats-output=influxdb mite.example:journey mite.example:datapool

# Two instances at once (INFLUXDB_* and INFLUXDB_*_SECONDARY)
mite scenario test --stats-output=influxdb --stats-output=influxdb:secondary mite.example:scenario
```

The test process runs one `Aggregator`
([mite/stats.py](https://github.com/sky-uk/mite/blob/master/mite/stats.py)) that
sends each stats dump to every output, so adding instances doesn't repeat the
aggregation. When the test finishes, the aggregator sends what it gathered since
its last dump and then closes the outputs, so the final partial interval isn't
lost.

### As an individual component (`mite exporter`)

InfluxDB writing can also run completely out-of-process, decoupled from the
test itself — useful when running distributed load tests (separate
`controller`/`runner`/`duplicator` processes) where stats are published to a
message bus rather than consumed in-process:

```bash
mite exporter --stats-out-socket=tcp://0.0.0.0:14305 --stats-output=influxdb --stats-output=influxdb:secondary
```

This binds a receiver to `--stats-out-socket` (the same socket `mite stats`
publishes dumped stats to) and sends every received dump to each output. The
same command can export to Prometheus too, by adding `--stats-output=prometheus`.

### Seeding metrics before a run (`influxdb init`)

```bash
# Default instance
mite influxdb init

# Named instances, as in --stats-output=influxdb:INSTANCE
mite influxdb init secondary 2
```

Writes a zero-valued point for every registered `mite_stats` entry point stat
(see [pyproject.toml](https://github.com/sky-uk/mite/blob/master/pyproject.toml)
`[project.entry-points.mite_stats]`) to each given InfluxDB instance, so
dashboards and alerts have a baseline series to chart against before the first
real test data point arrives (see
[mite/cli/influxdb.py](https://github.com/sky-uk/mite/blob/master/mite/cli/influxdb.py)).

### Testing

```bash
pytest test/test_influxdb_exporter.py
```

[test/test_influxdb_exporter.py](https://github.com/sky-uk/mite/blob/master/test/test_influxdb_exporter.py)
covers `InfluxCounter`, `InfluxGauge` and `InfluxHistogram` point conversion,
delta/cumulative field correctness, and histogram percentile math. These tests
exercise the stat model directly and do not require a running InfluxDB instance
or network access (no backend is constructed).

## Architecture

```{graphviz}
digraph influxdb_architecture {
    rankdir=LR;
    node [shape=box, fontname="sans-serif", fontsize=10];
    edge [fontname="sans-serif", fontsize=9];

    subgraph cluster_test {
        label="Test process";
        fontname="sans-serif";
        fontsize=10;
        style=dashed;
        J [label="Journeys"];
        S [label="Stats aggregator\nmite/stats.py"];
        J -> S [label="raw messages"];
    }

    IM [label="InfluxMetrics\nmite/web/influxdb.py"];
    W  [label="InfluxdbWriter"];
    B  [label="Backend adapter", shape=diamond];
    B1 [label="_InfluxV1Backend"];
    B2 [label="_InfluxV2Backend"];
    B3 [label="_InfluxV3Backend"];
    C1 [label="influxdb-client"];
    C2 [label="influxdb_client_3"];
    DB [label="InfluxDB", shape=cylinder];

    S  -> IM [label="dumped stats ~4x/sec"];
    IM -> W  [label="InfluxPoint batches"];
    W  -> B;
    B  -> B1 [label="v1"];
    B  -> B2 [label="v2"];
    B  -> B3 [label="v3"];
    B1 -> C1;
    B2 -> C1;
    B3 -> C2;
    C1 -> DB;
    C2 -> DB;
}
```

Files:

- [mite/web/influxdb.py](https://github.com/sky-uk/mite/blob/master/mite/web/influxdb.py)
  — core writer, stat aggregation/point conversion, and backend adapters
- [mite/web/\_\_init\_\_.py](https://github.com/sky-uk/mite/blob/master/mite/web/__init__.py)
  — Flask app exposing `/metrics` (Prometheus) and the `prometheus` stats output
- [mite/web/prometheus.py](https://github.com/sky-uk/mite/blob/master/mite/web/prometheus.py)
  — sibling Prometheus exporter (not covered here)

### Layers

1. **Stat model** (`InfluxStat`, `InfluxCounter`, `InfluxGauge`, `InfluxHistogram`)
   Mirror the shape of `mite.stats` types but render to `InfluxPoint` objects
   instead of Prometheus text. Each keeps running totals plus a
   `_prev_*` snapshot so that `to_points()` can emit both a delta (`value`,
   `count`, `sum`, percentiles computed from the delta buckets) and a
   cumulative value (`value_cumulative`, `count_cumulative`, ...) per flush.
   `InfluxHistogram` additionally reconstructs percentiles from histogram
   buckets (`_percentile_from_buckets`) and can optionally emit raw bucket
   points (`include_buckets=True`, Prometheus-style `le` tag) for exact
   reconstruction downstream.

2. **`InfluxMetrics`** (extends `InfluxdbWriter`)
   The `influxdb` stats output, created by `influxdb_output()` for each
   `--stats-output=influxdb[:INSTANCE]`. `send(message)` is called with a
   stats dump (a list of per-metric dicts produced by `mite.stats.Aggregator`). It creates/updates the
   relevant `InfluxStat` instances, buffers the resulting points, and flushes
   them to InfluxDB at a throttled cadence:
   - `MIN_FLUSH_INTERVAL = 1.0s` — stats dumps arrive roughly every 0.25s but
     a single Influx write can take longer, so points are buffered across
     several `send()` calls and flushed at a slower, steadier cadence.
   - `MAX_PENDING_POINTS = 5000` — hard cap on buffered points; oldest points
     are dropped (with an error log) if a stalled backend can't keep up, to
     bound memory on long-running tests.
   - A batch is only cleared from the pending buffer once `write_points()`
     actually accepted it (i.e. the write wasn't skipped) — otherwise a busy
     writer would silently lose points.

3. **`InfluxdbWriter`**
   The transport layer, independent of the stats model. Responsibilities:
   - Instantiates the correct backend adapter via `_create_influx_backend`.
   - Writes are asynchronous: a single-worker `ThreadPoolExecutor` plus a
     `BoundedSemaphore(1)` ensure **at most one write is ever in flight**. If
     a new batch of points arrives while a write is still pending,
     `write_points()` returns `None` immediately rather than blocking or
     queuing — i.e. writes are *fire-and-forget* and a slow backend causes
     batches to be skipped (and merged into the next flush by `InfluxMetrics`),
     never backpressure on the caller.
   - Skip accounting: logs a `WARNING` per skip, escalating to `ERROR` once
     `CONSECUTIVE_SKIP_ALERT_THRESHOLD` (50) consecutive skips occur, and
     every multiple thereof, so a backend that's permanently falling behind
     is visible without flooding logs under normal load spikes.
   - `close()` shuts down the executor (waiting for any in-flight write) and
     closes the underlying client.

4. **Backend adapters** (`_InfluxBackend` ABC)
   All adapters implement `write_points(points: list[InfluxPoint])` and
   `close()`, isolating the rest of the system from version-specific client
   APIs:
   - `_InfluxV2ClientBackend` — base class wrapping `influxdb_client.InfluxDBClient`
     with `SYNCHRONOUS` writes (used directly for v2).
   - `_InfluxV1Backend` — subclasses the v2 client backend, mapping the
     legacy `database`/`retention_policy`/`username:password` model onto the
     v2 client's `bucket`/`token` model (InfluxDB 1.8+ compatibility API).
   - `_InfluxV2Backend` — thin config wrapper around `_InfluxV2ClientBackend`.
   - `_InfluxV3Backend` — uses the separate `influxdb_client_3` package
     (`InfluxDBClient3`), InfluxDB's v3/IOx line.
   - Client imports are deferred (done inside `__init__`/`write_points`) so
     only the SDK needed for the configured version has to be installed.

   The version to use is selected via `_create_influx_backend` /
   `_create_single_backend`, which reads `INFLUXDB_VERSION` (via
   `packaging.version.Version`, so values like `1`, `2.0`, `v3` all parse —
   only the major version is used) and dispatches to the matching adapter,
   defaulting to v3 if unset.

### Multi-instance support

Every config lookup and class constructor accepts a `suffix` (e.g. `""`,
`"_2"`, `"_3"`, ...), allowing simultaneous writes to **N independent InfluxDB
instances** — e.g. `INFLUXDB_HOST` and `INFLUXDB_HOST_SECONDARY` configure two
different destinations. Each `--stats-output=influxdb:INSTANCE` creates one
`InfluxMetrics` with the suffix `_INSTANCE` (upper case); there's no limit on
the number of instances.

### Distributed topology

```{graphviz}
digraph influxdb_topology {
    rankdir=LR;
    node [shape=box, fontname="sans-serif", fontsize=10];
    edge [fontname="sans-serif", fontsize=9];

    R1  [label="runner"];
    R2  [label="runner"];
    D   [label="duplicator"];
    ST  [label="mite stats"];
    EXP [label="mite exporter"];
    DB  [label="InfluxDB", shape=cylinder];

    R1 -> D [label="messages"];
    R2 -> D [label="messages"];
    D  -> ST;
    ST -> EXP [label="stats-out-socket"];
    EXP -> DB;
}
```

## Configuration reference

Selected once via `INFLUXDB_VERSION{suffix}` (default `"v3"`; only the major
version matters: `1`, `2`, `3`). Remaining variables depend on the version:

| Version | Required env vars | Notes |
|---|---|---|
| v1 | `INFLUXDB_HOST`, `INFLUXDB_USERNAME`, `INFLUXDB_PASSWORD`, `INFLUXDB_DATABASE` | `INFLUXDB_RETENTION_POLICY` optional, defaults to `autogen`. Internally mapped to the v2 client (`bucket=database/retention_policy`, `token=username:password`, `org="-"`). |
| v2 | `INFLUXDB_HOST`, `INFLUXDB_TOKEN`, `INFLUXDB_BUCKET`, `INFLUXDB_ORG` | Uses `influxdb_client.InfluxDBClient` directly. |
| v3 | `INFLUXDB_HOST`, `INFLUXDB_TOKEN`, `INFLUXDB_DATABASE` | Uses `influxdb_client_3.InfluxDBClient3`. |

For another instance, suffix every variable with its name from
`--stats-output=influxdb:INSTANCE` in upper case (`INFLUXDB_VERSION_SECONDARY`,
`INFLUXDB_HOST_SECONDARY`, ...). `INFLUXDB_INCLUDE_BUCKETS{suffix}` is optional
and per instance.
Missing required variables raise `InfluxConfigError`
([mite/exceptions.py](https://github.com/sky-uk/mite/blob/master/mite/exceptions.py))
and abort writer creation.

## Key classes reference

| Class | Role |
|---|---|
| `InfluxPoint` | Plain dataclass: `measurement`, `tags`, `fields`, `time_ns` |
| `InfluxStat` / `InfluxCounter` / `InfluxGauge` / `InfluxHistogram` | Convert `mite.stats` dumps into `InfluxPoint`s, tracking deltas |
| `InfluxdbWriter` | Async, single-in-flight-write transport to a configured backend |
| `InfluxMetrics` | `InfluxdbWriter` subclass; buffers/throttles/flushes points from stats dumps |
| `_InfluxBackend` / `_InfluxV1Backend` / `_InfluxV2Backend` / `_InfluxV3Backend` | Version-specific client adapters |
| `influxdb_output` | `mite_stats_outputs` factory creating an `InfluxMetrics` per `--stats-output=influxdb[:INSTANCE]` |
