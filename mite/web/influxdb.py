import logging
import os
import threading
from collections import defaultdict
from dataclasses import dataclass
from influxdb_client_3 import InfluxDBClient3, Point
from time import time_ns
from concurrent.futures import ThreadPoolExecutor


logger = logging.getLogger(__name__)


@dataclass
class InfluxPoint:
    measurement: str
    tags: dict
    fields: dict
    time_ns: int


class InfluxdbWriter:
    def __init__(self):
        host = os.getenv("INFLUXDB_HOST")
        token = os.getenv("INFLUXDB_TOKEN")
        database = os.getenv("INFLUXDB_DATABASE")

        if not host or not token or not database:
            raise ValueError("INFLUXDB_HOST, INFLUXDB_DATABASE, and INFLUXDB_TOKEN variables are empty")

        self.client = InfluxDBClient3(
            host=host,
            token=token,
            database=database,
        )
        self._executor = ThreadPoolExecutor(max_workers=1)

    def _do_write(self, points):
        influx_points = []
        for point in points:
            influx_point = Point(point.measurement)
            for tag_key, tag_value in point.tags.items():
                influx_point.tag(tag_key, tag_value)
            for field_key, field_value in point.fields.items():
                influx_point.field(field_key, field_value)
            influx_point.time(point.time_ns)
            influx_points.append(influx_point)

        try:
            self.client.write(influx_points)
        except Exception as e:
            logger.warning(f"Failed to write to InfluxDB: {e}")

    def write_points(self, points):
        self._executor.submit(self._do_write, points)


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
