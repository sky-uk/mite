import logging
import os
from abc import abstractmethod, ABC
from dataclasses import dataclass
import time
from time import time_ns
from typing import cast
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore

from mite.exceptions import InfluxConfigError

from .totals import CounterTotals, GaugeTotals, HistogramTotals, RunningTotals


logger = logging.getLogger(__name__)


@dataclass
class InfluxPoint:
    measurement: str
    tags: dict
    fields: dict
    time_ns: int


class _InfluxBackend(ABC):
    @abstractmethod
    def write_points(self, points: list[InfluxPoint]) -> None: ...

    @abstractmethod
    def close(self) -> None: ...


def _client_points(point_type, points):
    from influxdb_client.domain.write_precision import WritePrecision

    client_points = []
    for point in points:
        client_point = point_type(point.measurement)
        for tag_key, tag_value in point.tags.items():
            client_point.tag(tag_key, tag_value)
        for field_key, field_value in point.fields.items():
            client_point.field(field_key, field_value)
        client_point.time(point.time_ns, write_precision=WritePrecision.NS)
        client_points.append(client_point)
    return client_points


class _InfluxDBClientBackend(_InfluxBackend):
    """InfluxDB 2, and InfluxDB 1.8+ through its v2 compatibility API."""

    def __init__(self, *, url, token, org, bucket):
        from influxdb_client.client.influxdb_client import InfluxDBClient
        from influxdb_client.client.write.point import Point
        from influxdb_client.client.write_api import SYNCHRONOUS

        self._bucket = bucket
        self._org = org
        self._point_type = Point
        self._client = InfluxDBClient(url=url, token=token, org=org)
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)

    def write_points(self, points: list[InfluxPoint]) -> None:
        from influxdb_client.domain.write_precision import WritePrecision

        self._write_api.write(
            bucket=self._bucket,
            org=self._org,
            record=_client_points(self._point_type, points),
            write_precision=cast(WritePrecision, WritePrecision.NS),
        )

    def close(self) -> None:
        self._client.close()


class _InfluxDBClient3Backend(_InfluxBackend):
    def __init__(self, *, url, token, database):
        from influxdb_client_3 import InfluxDBClient3, Point

        self._point_type = Point
        self._client = InfluxDBClient3(host=url, token=token, database=database)

    def write_points(self, points: list[InfluxPoint]) -> None:
        self._client.write(_client_points(self._point_type, points))

    def close(self) -> None:
        self._client.close()


_COMMON_PARAMS = ("buckets", "tls")


def _secret(url, param, default):
    name = url.params.get(param, default)
    value = os.getenv(name)
    if not value:
        raise InfluxConfigError(
            f"Stats output {url}: environment variable {name} is not set"
        )
    return value


def influxdb_backend(url):
    """Create the InfluxDB client backend for an ``influxdb1://``,
    ``influxdb2://`` or ``influxdb3://`` stats output URL (see
    :func:`influxdb_output`)."""
    if url.host is None:
        raise url.error("expected a host, e.g. influxdb3://influx.example:8181/DATABASE")
    host = f"[{url.host}]" if ":" in url.host else url.host
    port = f":{url.port}" if url.port is not None else ""
    base_url = f"{'https' if url.flag('tls') else 'http'}://{host}{port}"

    if url.scheme == "influxdb1":
        url.check(
            paths=(("database",), ("database", "retention_policy")),
            params=_COMMON_PARAMS + ("username_env", "password_env"),
        )
        username = _secret(url, "username_env", "INFLUXDB_USERNAME")
        password = _secret(url, "password_env", "INFLUXDB_PASSWORD")
        database, retention_policy = (url.path + ("autogen",))[:2]
        return _InfluxDBClientBackend(
            url=base_url,
            token=f"{username}:{password}",
            org="-",
            bucket=f"{database}/{retention_policy}",
        )
    if url.scheme == "influxdb2":
        url.check(paths=(("org", "bucket"),), params=_COMMON_PARAMS + ("token_env",))
        org, bucket = url.path
        return _InfluxDBClientBackend(
            url=base_url,
            token=_secret(url, "token_env", "INFLUXDB_TOKEN"),
            org=org,
            bucket=bucket,
        )
    if url.scheme == "influxdb3":
        url.check(paths=(("database",),), params=_COMMON_PARAMS + ("token_env",))
        return _InfluxDBClient3Backend(
            url=base_url,
            token=_secret(url, "token_env", "INFLUXDB_TOKEN"),
            database=url.path[0],
        )
    raise url.error("expected an influxdb1://, influxdb2:// or influxdb3:// URL")


class InfluxdbWriter:
    # After this many consecutive skipped writes (previous write still in
    # flight), escalate to an ERROR log -- a handful of skips under a load
    # spike is normal backpressure, but a sustained run means the backend
    # can't keep up at all and this needs to be visible, not just noise at
    # WARNING level.
    CONSECUTIVE_SKIP_ALERT_THRESHOLD = 50

    def __init__(self, backend):
        self._backend = backend
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._write_slots = BoundedSemaphore(value=1)
        self._skipped_writes = 0
        self._consecutive_skips = 0

    def _do_write(self, points):
        self._backend.write_points(points)

    def write_points(self, points):
        if not self._write_slots.acquire(blocking=False):
            self._skipped_writes += 1
            self._consecutive_skips += 1
            if self._consecutive_skips == self.CONSECUTIVE_SKIP_ALERT_THRESHOLD:
                logger.error(
                    "InfluxDB writer has skipped %d consecutive writes -- the backend is "
                    "not keeping up with the current write cadence",
                    self._consecutive_skips,
                )
            elif self._consecutive_skips % self.CONSECUTIVE_SKIP_ALERT_THRESHOLD == 0:
                logger.error(
                    "InfluxDB writer is still falling behind: %d consecutive writes skipped "
                    "(%d total)",
                    self._consecutive_skips, self._skipped_writes,
                )
            else:
                logger.warning(
                    "Skipping InfluxDB write because a previous write is still pending "
                    "(%d skipped so far, this batch had %d points)",
                    self._skipped_writes, len(points),
                )
            return None

        self._consecutive_skips = 0
        try:
            future = self._executor.submit(self._do_write, points)
        except Exception:
            self._write_slots.release()
            raise

        future.add_done_callback(self._complete_write)
        return future

    def _complete_write(self, future):
        self._write_slots.release()
        try:
            future.result()
        except Exception:
            logger.exception("Failed to write to InfluxDB")

    def close(self):
        self._executor.shutdown(wait=True)
        self._backend.close()

PERCENTILES = (50, 75, 90, 95, 99)


def _percentiles(bins, bin_counts, total):
    """Estimate PERCENTILES from cumulative bin counts, interpolating linearly
    within a bin; values past the last bin are reported as the last bin."""
    if total == 0:
        return {f"p{p}": 0.0 for p in PERCENTILES}

    result = {}
    for p in PERCENTILES:
        target = p / 100 * total
        prev_count = 0
        prev_bound = 0.0
        for bound, count in zip(bins, bin_counts):
            if count >= target:
                if count == prev_count:
                    result[f"p{p}"] = float(bound)
                else:
                    fraction = (target - prev_count) / (count - prev_count)
                    result[f"p{p}"] = float(prev_bound + fraction * (bound - prev_bound))
                break
            prev_count = count
            prev_bound = bound
        else:
            result[f"p{p}"] = float(bins[-1])
    return result


# Each stat type is written with fixed field types (InfluxDB rejects a field
# that changes type), so counters are always ints and gauges always floats.


def _counter_points(totals, summary, tns, include_buckets):
    return [
        InfluxPoint(
            measurement=totals.name,
            tags=dict(zip(totals.labels, key)),
            fields={"value": int(value), "value_cumulative": int(totals.values[key])},
            time_ns=tns,
        )
        for key, value in summary["metrics"].items()
    ]


def _gauge_points(totals, summary, tns, include_buckets):
    return [
        InfluxPoint(
            measurement=totals.name,
            tags=dict(zip(totals.labels, key)),
            fields={"value": float(value)},
            time_ns=tns,
        )
        for key, value in summary["metrics"].items()
    ]


def _histogram_fields(bins, bin_counts, total, total_sum, suffix=""):
    fields = {f"{name}{suffix}": value for name, value in _percentiles(bins, bin_counts, total).items()}
    fields[f"sum{suffix}"] = float(total_sum)
    fields[f"count{suffix}"] = int(total)
    fields[f"avg{suffix}"] = total_sum / total if total > 0 else 0.0
    return fields


def _histogram_points(totals, summary, tns, include_buckets):
    no_counts = [0] * len(totals.bins)
    keys = set(summary["total_counts"]) | set(summary["sums"]) | set(summary["bin_counts"])
    points = []
    for key in sorted(keys):
        tags = dict(zip(totals.labels, key))
        bin_counts = totals.bin_counts.get(key, no_counts)
        total = totals.total_counts.get(key, 0)
        fields = _histogram_fields(
            totals.bins,
            summary["bin_counts"].get(key, no_counts),
            summary["total_counts"].get(key, 0),
            summary["sums"].get(key, 0),
        )
        fields.update(
            _histogram_fields(totals.bins, bin_counts, total, totals.sums.get(key, 0), "_cumulative")
        )
        points.append(
            InfluxPoint(measurement=f"{totals.name}_summary", tags=tags, fields=fields, time_ns=tns)
        )
        if include_buckets:
            for bin_label, bin_count in zip(totals.bins, bin_counts):
                points.append(InfluxPoint(
                    measurement=f"{totals.name}_bucket",
                    tags={**tags, "le": str(bin_label)},
                    fields={"count": int(bin_count)},
                    time_ns=tns,
                ))
            points.append(InfluxPoint(
                measurement=f"{totals.name}_bucket",
                tags={**tags, "le": "+Inf"},
                fields={"count": int(total)},
                time_ns=tns,
            ))
    return points


_POINT_BUILDERS = {
    CounterTotals: _counter_points,
    GaugeTotals: _gauge_points,
    HistogramTotals: _histogram_points,
}


def _points(updated, tns, include_buckets=False):
    points = []
    for totals, summary in updated:
        points.extend(_POINT_BUILDERS[type(totals)](totals, summary, tns, include_buckets))
    return points


def influxdb_init_points(dumps, tns):
    """Zero-valued points for every stat in ``dumps`` (as produced by a fresh
    aggregation), with every tag set to ``__init__``, so dashboards have a
    series to chart before the first real data arrives. Written by
    ``mite influxdb init`` with the same fields as real data."""
    zero_dump = []
    for summary in dumps:
        key = ("__init__",) * len(summary["labels"])
        if summary["type"] == "Histogram":
            zero_dump.append({
                **summary,
                "bin_counts": {key: [0] * len(summary["bins"])},
                "sums": {key: 0.0},
                "total_counts": {key: 0},
            })
        else:
            zero_dump.append({**summary, "metrics": {key: 0}})
    return _points(RunningTotals().update(zero_dump), tns)


class InfluxMetrics(InfluxdbWriter):
    # Aggregator dumps every ~0.25s (shared with the other stats outputs, so that
    # cadence can't be changed here), but a single InfluxDB write consistently
    # takes longer than that under load, so points are buffered across
    # several send() calls and only actually written at this slower
    # cadence instead of dropping batches via the writer's semaphore.
    MIN_FLUSH_INTERVAL = 1.0
    # Hard cap on buffered points so a stalled/unreachable backend can't grow
    # memory unbounded over a long test run, so oldest points are dropped.
    MAX_PENDING_POINTS = 5000

    def __init__(self, backend, include_buckets=False):
        super().__init__(backend)
        self.include_buckets = include_buckets
        self.totals = RunningTotals()
        self._pending_points = []
        self._last_flush_time = time.monotonic()

    def send(self, message):
        logger.debug("dump received by influxdb metrics: %s", message)
        self._pending_points.extend(
            _points(self.totals.update(message), time_ns(), self.include_buckets)
        )

        if len(self._pending_points) > self.MAX_PENDING_POINTS:
            dropped = len(self._pending_points) - self.MAX_PENDING_POINTS
            self._pending_points = self._pending_points[-self.MAX_PENDING_POINTS:]
            logger.error(
                "InfluxDB pending point backlog exceeded %d, dropped %d oldest points",
                self.MAX_PENDING_POINTS, dropped,
            )

        now = time.monotonic()
        if self._pending_points and now - self._last_flush_time >= self.MIN_FLUSH_INTERVAL:
            future = self.write_points(self._pending_points)
            if future is not None:
                # only clear once the batch was actually accepted for writing
                # otherwise we'd silently drop points on a busy writer
                self._pending_points = []
                self._last_flush_time = now

    def close(self):
        if self._pending_points:
            self.write_points(self._pending_points)
            self._pending_points = []
        super().close()


def influxdb_output(url, opts):
    """``mite_stats_outputs`` factory for ``influxdb1://``, ``influxdb2://``
    and ``influxdb3://`` URLs::

        influxdb1://HOST[:PORT]/DATABASE[/RETENTION_POLICY]
        influxdb2://HOST[:PORT]/ORG/BUCKET
        influxdb3://HOST[:PORT]/DATABASE

    Query parameters:

    * ``tls=true``: connect over https (default http).
    * ``buckets=true``: also write raw histogram bucket points.
    * ``token_env`` (v2, v3): environment variable holding the API token,
      default ``INFLUXDB_TOKEN``.
    * ``username_env``, ``password_env`` (v1): environment variables holding
      the credentials, default ``INFLUXDB_USERNAME`` and ``INFLUXDB_PASSWORD``.
      The retention policy defaults to ``autogen``.
    """
    return InfluxMetrics(influxdb_backend(url), include_buckets=url.flag("buckets"))
