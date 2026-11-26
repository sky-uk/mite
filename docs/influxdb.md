# InfluxDB

Mite can write live test metrics (counters, gauges, histograms) to InfluxDB
v1, v2, or v3, either as part of an in-process test run or as a standalone
exporter process consuming stats from the message bus.

It converts the internal stats model (`Counter`, `Gauge`, `Histogram` — see
[mite/stats.py](https://github.com/sky-uk/mite/blob/master/mite/stats.py)) into
InfluxDB line-protocol points and writes them to one or more InfluxDB instances.

## Quick start

### Configuration

Each InfluxDB server is one `--stats-output` URL. The scheme selects the
InfluxDB version:

```text
influxdb1://HOST[:PORT]/DATABASE[/RETENTION_POLICY]
influxdb2://HOST[:PORT]/ORG/BUCKET
influxdb3://HOST[:PORT]/DATABASE
```

Query parameters:

| Parameter | Versions | Meaning |
|---|---|---|
| `tls=true` | all | Connect over https (default http) |
| `buckets=true` | all | Also write raw histogram bucket points (`le`-tagged, Prometheus-style) alongside the computed percentiles |
| `token_env=NAME` | v2, v3 | Environment variable holding the API token (default `INFLUXDB_TOKEN`) |
| `username_env=NAME`, `password_env=NAME` | v1 | Environment variables holding the credentials (default `INFLUXDB_USERNAME`, `INFLUXDB_PASSWORD`) |

Credentials never go in the URL, where they'd show up in process lists and
logs: a URL containing `user:password@` or `token@` is rejected, with the
credentials masked in the error. Unknown parameters, a missing host, the wrong
number of path segments, or an unset credential variable are errors too.

### Via `mite` test run (in-process)

Pass `--stats-output` once per InfluxDB server:

```bash
mite journey test --stats-output=influxdb3://localhost:8181/mite mite.example:journey mite.example:datapool

# Two servers at once, each with its own token
mite scenario test \
    --stats-output=influxdb3://influx-a:8181/mite?token_env=INFLUX_A_TOKEN \
    --stats-output=influxdb1://influx-b:8086/mite?buckets=true \
    mite.example:scenario
```

The test process runs one `Aggregator`
([mite/stats.py](https://github.com/sky-uk/mite/blob/master/mite/stats.py)) that
sends each stats dump to every output, so adding servers doesn't repeat the
aggregation. When the test finishes, the aggregator sends what it gathered since
its last dump and then closes the outputs, so the final partial interval isn't
lost.

### As an individual component (`mite exporter`)

InfluxDB writing can also run completely out-of-process, decoupled from the
test itself — useful when running distributed load tests (separate
`controller`/`runner`/`duplicator` processes) where stats are published to a
message bus rather than consumed in-process:

```bash
mite exporter --stats-out-socket=tcp://0.0.0.0:14305 --stats-output=influxdb3://influx-a:8181/mite
```

This binds a receiver to `--stats-out-socket` (the same socket `mite stats`
publishes dumped stats to) and sends every received dump to each output. The
same command can export to Prometheus too, by adding
`--stats-output=prometheus://0.0.0.0:9301`.

### Seeding metrics before a run (`influxdb init`)

```bash
mite influxdb init influxdb3://influx-a:8181/mite influxdb1://influx-b:8086/mite
```

Takes the same URLs as `--stats-output`, and writes a zero-valued point for
every registered `mite_stats` entry point stat
(see [pyproject.toml](https://github.com/sky-uk/mite/blob/master/pyproject.toml)
`[project.entry-points.mite_stats]`) to each one, so
dashboards and alerts have a baseline series to chart against before the first
real test data point arrives (see
[mite/cli/influxdb.py](https://github.com/sky-uk/mite/blob/master/mite/cli/influxdb.py)).

### Testing

```bash
pytest test/test_influxdb_exporter.py
```

[test/test_influxdb_exporter.py](https://github.com/sky-uk/mite/blob/master/test/test_influxdb_exporter.py)
covers point conversion for counters, gauges and histograms, the change and
cumulative fields, histogram percentiles, and `influxdb init` points. These
tests use a mock backend and don't need a running InfluxDB instance or network
access.

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

    IM [label="InfluxMetrics\nmite/stats_outputs/influxdb.py"];
    W  [label="InfluxdbWriter"];
    B  [label="influxdb_backend(url)", shape=diamond];
    B1 [label="_InfluxDBClientBackend"];
    B3 [label="_InfluxDBClient3Backend"];
    C1 [label="influxdb-client"];
    C2 [label="influxdb_client_3"];
    DB [label="InfluxDB", shape=cylinder];

    S  -> IM [label="dumped stats ~4x/sec"];
    IM -> W  [label="InfluxPoint batches"];
    W  -> B;
    B  -> B1 [label="influxdb1://, influxdb2://"];
    B  -> B3 [label="influxdb3://"];
    B1 -> C1;
    B3 -> C2;
    C1 -> DB;
    C2 -> DB;
}
```

Files:

- [mite/stats_outputs/influxdb.py](https://github.com/sky-uk/mite/blob/master/mite/stats_outputs/influxdb.py)
  — point conversion, writer and backend adapters
- [mite/stats_outputs/cumulative.py](https://github.com/sky-uk/mite/blob/master/mite/stats_outputs/cumulative.py)
  — cumulative values of the aggregator's dumps, shared with the Prometheus output
- [mite/stats_outputs/\_\_init\_\_.py](https://github.com/sky-uk/mite/blob/master/mite/stats_outputs/__init__.py)
  — `--stats-output` URL parsing and loading
- [mite/stats_outputs/prometheus.py](https://github.com/sky-uk/mite/blob/master/mite/stats_outputs/prometheus.py)
  — the `prometheus://` stats output (not covered here)

### Layers

1. **Points** (`_counter_points`, `_gauge_points`, `_histogram_points`)
   Each aggregator dump holds what changed since the previous dump, and
   `CumulativeStats` (`mite/stats_outputs/cumulative.py`, also used by the
   Prometheus output) adds it to the values since the start of the run. Each stat in a dump
   becomes points with both: the change (`value`, `count`, `sum`, `avg`, and
   percentiles from the change's bucket counts) and the total
   (`value_cumulative`, `count_cumulative`, ...). Only label combinations in the
   dump are written. Percentiles are estimated from the histogram buckets
   (`_percentiles`), and raw cumulative bucket points can be added (`buckets=true`,
   Prometheus-style `le` tag) for exact reconstruction downstream. Counters are
   always written as integers and gauges as floats, because InfluxDB rejects a
   field that changes type. `influxdb_init_points` builds the `influxdb init`
   points the same way, from zero values. A stat with an unknown dump `"type"`
   is skipped, with an error logged once.

2. **`InfluxMetrics`** (extends `InfluxdbWriter`)
   The `influxdb` stats output, created by `influxdb_output()` for each
   `influxdb1://`, `influxdb2://` or `influxdb3://` `--stats-output` URL. `send(message)` is called with a
   stats dump (a list of per-metric dicts produced by `mite.stats.Aggregator`). It converts the
   dump to points, buffers them, and flushes
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
   - Writes through the backend adapter it is given (see `influxdb_backend`).
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
   - `_InfluxDBClientBackend` — wraps `influxdb_client.InfluxDBClient` with
     `SYNCHRONOUS` writes. Used for v2, and for v1 through InfluxDB 1.8+'s v2
     compatibility API (`bucket=DATABASE/RETENTION_POLICY`,
     `token=USERNAME:PASSWORD`, `org="-"`).
   - `_InfluxDBClient3Backend` — uses the separate `influxdb_client_3` package
     (`InfluxDBClient3`), InfluxDB's v3/IOx line.
   - Client imports are deferred (done inside `__init__`/`write_points`) so
     only the SDK needed for the configured version has to be installed.

   `influxdb_backend(url)` builds the adapter from a `--stats-output` URL,
   choosing it by the URL scheme.

### Multiple servers

Each `--stats-output` URL creates its own `InfluxMetrics`, writer and backend,
so there's no limit on the number of InfluxDB servers, and servers of different
versions can be mixed.

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

## Key classes reference

| Class | Role |
|---|---|
| `InfluxPoint` | Plain dataclass: `measurement`, `tags`, `fields`, `time_ns` |
| `CumulativeStats` (`mite/stats_outputs/cumulative.py`) | Cumulative values of every dump so far, shared with the Prometheus output |
| `InfluxdbWriter` | Async, single-in-flight-write transport to a configured backend |
| `InfluxMetrics` | `InfluxdbWriter` subclass; buffers/throttles/flushes points from stats dumps |
| `_InfluxBackend` / `_InfluxDBClientBackend` / `_InfluxDBClient3Backend` | Version-specific client adapters, built by `influxdb_backend(url)` |
| `influxdb_output` | `mite_stats_outputs` factory for `influxdb1://`, `influxdb2://` and `influxdb3://` URLs |
