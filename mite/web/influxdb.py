import logging
import os
from abc import abstractmethod, ABC
import threading
from collections import defaultdict
from dataclasses import dataclass
import time
from time import time_ns
from typing import cast
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore

from mite.exceptions import InfluxConfigError


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

class InfluxStat:
    def __init__(self, name, message):
        self._lock = threading.Lock()
        self.name = name
        self.labels = message["labels"]
        self.metrics = defaultdict(float, message["metrics"])

    def to_points(self, time_ns, touched_keys=None):
        points = []
        with self._lock:
            for k, v in self.metrics.items() if touched_keys is None else (
                (k, self.metrics[k]) for k in touched_keys):
                tags = dict(zip(self.labels, k))
                points.append(InfluxPoint(
                    measurement=self.name,
                    tags=tags,
                    fields={"value": v},
                    time_ns=time_ns,
                ))
        return points


class InfluxCounter(InfluxStat):
    def __init__(self, name, message):
        super().__init__(name, message)
        self.metrics = defaultdict(int, {k: int(v) for k, v in message["metrics"].items()})
        self._prev_metrics = defaultdict(int)

    def update(self, message):
        touched_keys = set()
        with self._lock:
            for k, v in message["metrics"].items():
                self.metrics[k] += int(v)
                touched_keys.add(k)
        return touched_keys

    def to_points(self, time_ns, touched_keys=None):
        points = []
        with self._lock:
            for k, v in self.metrics.items() if touched_keys is None else (
                (k, self.metrics[k]) for k in touched_keys):
                tags = dict(zip(self.labels, k))
                delta = max(0, v - self._prev_metrics[k])
                points.append(InfluxPoint(
                    measurement=self.name,
                    tags=tags,
                    fields={"value": delta, "value_cumulative": v},
                    time_ns=time_ns,
                ))
                self._prev_metrics[k] = v
        return points

class InfluxGauge(InfluxStat):
    def __init__(self, name, message):
        super().__init__(name, message)
        self.metrics = defaultdict(float, {k: float(v) for k, v in message["metrics"].items()})
    def update(self, message):
        touched_keys = set()
        with self._lock:
            for k, v in message["metrics"].items():
                self.metrics[k] = float(v)
                touched_keys.add(k)
        return touched_keys


class InfluxHistogram(InfluxStat):

    PERCENTILES = [0.50, 0.75, 0.90, 0.95, 0.99]

    def __init__(self, name, message, include_buckets=False):
        self._lock = threading.Lock()
        self.name = name
        self.labels = message["labels"]
        self.bins = tuple(message["bins"])
        self.include_buckets = include_buckets

        self.bin_counts = defaultdict(lambda: [0] * len(self.bins))
        self.sums = defaultdict(float)
        self.total_counts = defaultdict(int)

        self._prev_bin_counts = defaultdict(lambda: [0] * len(self.bins))
        self._prev_sums = defaultdict(float)
        self._prev_total_counts = defaultdict(int)

        for k, v in message.get("bin_counts", {}).items():
            self.bin_counts[k] = list(v)
        for k, v in message.get("total_counts", {}).items():
            self.total_counts[k] = int(v)
        for k, v in message.get("sums", {}).items():
            self.sums[k] = float(v)

    def update(self, message):
        touched_keys = set()
        with self._lock:
            for k, v in message["total_counts"].items():
                self.total_counts[k] += int(v)
                touched_keys.add(k)
            for k, v in message["sums"].items():
                self.sums[k] += float(v)
                touched_keys.add(k)
            for k, v in message["bin_counts"].items():
                bin_counts = self.bin_counts[k]
                for i, count in enumerate(v):
                    bin_counts[i] += int(count)
                touched_keys.add(k)
        return touched_keys

    def _percentile_from_buckets(self, bin_counts, total):
        if total == 0:
            return {f"p{int(p*100)}": 0.0 for p in self.PERCENTILES}

        result = {}
        for p in self.PERCENTILES:
            target = p * total
            prev_count = 0
            prev_bound = 0.0

            for bound, count in zip(self.bins, bin_counts):
                if count >= target:
                    if count == prev_count:
                        result[f"p{int(p*100)}"] = float(bound)
                    else:
                        fraction = (target - prev_count) / (count - prev_count)
                        result[f"p{int(p*100)}"] = float(prev_bound + fraction * (bound - prev_bound))
                    break
                prev_count = count
                prev_bound = bound
            else:
                result[f"p{int(p*100)}"] = float(self.bins[-1])
        return result

    def _calculate_delta(self, k):
        current_bin_counts = self.bin_counts[k]
        prev_bin_counts = self._prev_bin_counts[k]
        delta_bin_counts = [max(0, c - p) for c, p in zip(current_bin_counts, prev_bin_counts)]
        delta_total = max(0, self.total_counts[k] - self._prev_total_counts[k])
        delta_sum = max(0.0, self.sums[k] - self._prev_sums[k])
        return delta_bin_counts, delta_total, delta_sum

    def to_points(self, time_ns, touched_keys=None):
        points = []
        with self._lock:
            keys_to_iterate = self.total_counts if touched_keys is None else touched_keys

            for k in sorted(keys_to_iterate):
                tags = dict(zip(self.labels, k))
                bin_counts = self.bin_counts[k]
                total = self.total_counts[k]
                message_sum = self.sums[k]

                delta_bin_counts, delta_total, delta_sum = self._calculate_delta(k)

                cumulative_percentile = self._percentile_from_buckets(bin_counts, total)
                delta_percentile = self._percentile_from_buckets(delta_bin_counts, delta_total)

                fields = {
                    "p50": delta_percentile["p50"],
                    "p75": delta_percentile["p75"],
                    "p90": delta_percentile["p90"],
                    "p95": delta_percentile["p95"],
                    "p99": delta_percentile["p99"],
                    "sum": delta_sum,
                    "count": delta_total,
                    "avg": delta_sum / delta_total if delta_total > 0 else 0.0,
                    "p50_cumulative": cumulative_percentile["p50"],
                    "p75_cumulative": cumulative_percentile["p75"],
                    "p90_cumulative": cumulative_percentile["p90"],
                    "p95_cumulative": cumulative_percentile["p95"],
                    "p99_cumulative": cumulative_percentile["p99"],
                    "sum_cumulative": message_sum,
                    "count_cumulative": total,
                    "avg_cumulative": message_sum / total if total > 0 else 0.0,
                }

                points.append(InfluxPoint(
                    measurement=f"{self.name}_summary",
                    tags=tags,
                    fields=fields,
                    time_ns=time_ns,
                ))

                if self.include_buckets:
                    for bin_label, bin_count in zip(self.bins, bin_counts):
                        points.append(InfluxPoint(
                            measurement=f"{self.name}_bucket",
                            tags={**tags, "le": str(bin_label)},
                            fields={"count": int(bin_count)},
                            time_ns=time_ns,
                        ))

                    points.append(InfluxPoint(
                        measurement=f"{self.name}_bucket",
                        tags={**tags, "le": "+Inf"},
                        fields={"count": int(total)},
                        time_ns=time_ns,
                    ))

                self._prev_bin_counts[k] = list(bin_counts)
                self._prev_total_counts[k] = total
                self._prev_sums[k] = message_sum

        return points


INFLUX_STAT_TYPES = {"Counter": InfluxCounter, "Gauge": InfluxGauge, "Histogram": InfluxHistogram}

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
        self.stats = {}
        self._pending_points = []
        self._last_flush_time = time.monotonic()

    def send(self, message):
        logger.debug(f"message to iterate in influxdb metrics: {message}")
        dirty_keys = {}
        for stat in message:
            name = stat["name"]
            if name not in self.stats:
                if stat["type"] == "Histogram":
                    self.stats[name] = InfluxHistogram(name, stat, include_buckets=self.include_buckets)
                else:
                    self.stats[name] = INFLUX_STAT_TYPES[stat["type"]](name, stat)
                dirty_keys[name] = None
            else:
                dirty_keys[name] = self.stats[name].update(stat)

        tns = time_ns()
        for name, stat in self.stats.items():
            if name in dirty_keys:
                self._pending_points.extend(stat.to_points(tns, touched_keys=dirty_keys[name]))

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
