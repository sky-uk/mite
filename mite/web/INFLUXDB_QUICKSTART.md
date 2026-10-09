# InfluxDB Quickstart

Short reference for configuring and running Mite's InfluxDB integration. For
architecture details see [README.md](README.md).

## Intro

Mite can write live test metrics (counters, gauges, histograms) to InfluxDB
v1, v2, or v3, either as part of an in-process test run or as a standalone
exporter process consuming stats from the message bus.

## Configuration (environment variables)

Set `INFLUXDB_VERSION` to select the client (default `v3`), then the
matching variables below. For additional simultaneous instances, suffix
every variable with `_2`, `_3`, etc.

| Version | Required env vars |
|---|---|
| v1 | `INFLUXDB_HOST`, `INFLUXDB_USERNAME`, `INFLUXDB_PASSWORD`, `INFLUXDB_DATABASE` (optional `INFLUXDB_RETENTION_POLICY`, default `autogen`) |
| v2 | `INFLUXDB_HOST`, `INFLUXDB_TOKEN`, `INFLUXDB_BUCKET`, `INFLUXDB_ORG` |
| v3 | `INFLUXDB_HOST`, `INFLUXDB_TOKEN`, `INFLUXDB_DATABASE` |

## Usage

### Via `mite` test run (in-process)

```bash
mite journey test --influxdb=1 mite.example:journey mite.example:datapool
mite scenario test --influxdb=2 mite.example:scenario   # two instances at once
mite scenario test --influxdb=1 --include-buckets mite.example:scenario
```

`--include-buckets` additionally emits raw histogram bucket points (`le`-tagged,
Prometheus-style) alongside the computed percentiles, letting downstream tools
reconstruct exact distributions instead of relying on pre-computed percentiles.

### As an individual component (`influxdb_exporter`)

```bash
mite influxdb_exporter --stats-out-socket=tcp://0.0.0.0:14305
```

Binds to the socket `mite stats` publishes dumps to and writes to InfluxDB
independently of any test process. Only the unsuffixed, single-instance env
vars are read (no `--influxdb=N` support here). `--include-buckets` can
optionally be passed here too, same as for the in-process test run.

To write to multiple InfluxDB instances, run multiple `influxdb_exporter`
processes, each with its own (unsuffixed) env vars pointed at a different
instance — there's no built-in multi-instance support in this component,
unlike the `--influxdb=N` in-process mode.

## Seeding

```bash
mite influxdb init --influxdb=2
```

Writes a zero-valued point for every registered `mite_stats` entry point
stat to each configured instance, so dashboards have a baseline series
before real test data arrives.

## Testing

```bash
pytest test/test_influxdb_exporter.py
```

Covers `InfluxCounter`/`InfluxGauge`/`InfluxHistogram` point conversion and
delta/cumulative math directly against the stat model — no InfluxDB instance
or network access required.
