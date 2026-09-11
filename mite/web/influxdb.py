import logging
import os
import threading
from collections import defaultdict
from dataclasses import dataclass
from time import time_ns
from typing import cast
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore
from packaging.version import Version, InvalidVersion

from mite.exceptions import InfluxConfigError


logger = logging.getLogger(__name__)


@dataclass
class InfluxPoint:
    measurement: str
    tags: dict
    fields: dict
    time_ns: int


class InfluxdbWriter:
    def __init__(self):
        raw_version = os.getenv("INFLUXDB_VERSION", "v3")
        try:
            self.major_version = Version(raw_version).major
        except (TypeError, InvalidVersion):
            raise ValueError(f"Invalid INFLUXDB_VERSION: {raw_version}")
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._write_slots = BoundedSemaphore(value=1)
        try:
            self._create_client()
        except Exception as e:
            logger.exception(f"Failed to create InfluxDB client: {e}")
            raise

    def _create_client(self):
        if self.major_version == 3:
            from influxdb_client_3 import InfluxDBClient3, Point as V3Point
            host = os.getenv("INFLUXDB_HOST")
            token = os.getenv("INFLUXDB_TOKEN")
            database = os.getenv("INFLUXDB_DATABASE")

            if not host or not token or not database:
                raise InfluxConfigError("Missing Influxdb config")

            self.v3_client = InfluxDBClient3(
                host=host,
                token=token,
                database=database,
            )
            self.V3Point = V3Point
        else:
            from influxdb_client.client.influxdb_client import InfluxDBClient
            from influxdb_client.client.write.point import Point as V2Point
            from influxdb_client.client.write_api import SYNCHRONOUS

            if self.major_version == 1:
                host = os.getenv("INFLUXDB_HOST")
                username = os.getenv("INFLUXDB_USERNAME")
                password = os.getenv("INFLUXDB_PASSWORD")
                database = os.getenv("INFLUXDB_DATABASE")

                if not host or not username or not password or not database:
                    raise InfluxConfigError("Missing Influxdb config")

                retention_policy = os.getenv("INFLUXDB_RETENTION_POLICY", "autogen")
                self.bucket = f"{database}/{retention_policy}"
                self.org = "-"

                self.v2_client = InfluxDBClient(
                    url=host,
                    token=f"{username}:{password}",
                    org=self.org,
                )

            elif self.major_version == 2:
                host = os.getenv("INFLUXDB_HOST")
                token = os.getenv("INFLUXDB_TOKEN")
                bucket = os.getenv("INFLUXDB_BUCKET")
                org = os.getenv("INFLUXDB_ORG")

                if not host or not token or not bucket or not org:
                    raise InfluxConfigError("Missing Influxdb config")

                self.bucket = bucket
                self.org = org

                self.v2_client = InfluxDBClient(
                    url=host,
                    token=token,
                    org=org,
                )
            else:
                raise InfluxConfigError(f"Unsupported InfluxDB major version: {self.major_version}")
            self.V2Point = V2Point
            self.v2_write_api = self.v2_client.write_api(write_options=SYNCHRONOUS)


    def _do_write(self, points):
        from influxdb_client.domain.write_precision import WritePrecision
        influx_points = []
        for point in points:
            if self.major_version == 3:
                influx_point = self.V3Point(point.measurement)
            else:
                influx_point = self.V2Point(point.measurement)
            for tag_key, tag_value in point.tags.items():
                influx_point.tag(tag_key, tag_value)
            for field_key, field_value in point.fields.items():
                influx_point.field(field_key, field_value)
            influx_point.time(point.time_ns, write_precision=WritePrecision.NS)
            influx_points.append(influx_point)

        if self.major_version == 3:
            self.v3_client.write(influx_points)
        else:
            self.v2_write_api.write(
                bucket=self.bucket,
                org=self.org,
                record=influx_points,
                write_precision=cast(WritePrecision, WritePrecision.NS))

    def write_points(self, points):
        if not self._write_slots.acquire(blocking=False):
            logger.warning("Skipping InfluxDB write because a previous write is still pending")
            return None

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
        client = getattr(self, "v3_client", None) or getattr(self, "v2_client", None)
        if client is not None:
            client.close()


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
    def __init__(self, include_buckets=False):
        super().__init__()
        self.include_buckets = include_buckets
        self.stats = {}

    def process(self, message):
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

        points = []
        tns = time_ns()
        for name, stat in self.stats.items():
            if name in dirty_keys:
                points.extend(stat.to_points(tns, touched_keys=dirty_keys[name]))
        if points:
            self.write_points(points)
