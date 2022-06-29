import logging
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)


def format_dict(d):
    return ",".join(
        [
            '%s="%s"' % (k, str(v).replace("\\", "\\\\").replace('"', '\\"'))
            for k, v in d.items()
        ]
    )


class PrometheusStat:
    def __init__(self, name, message):
        self._lock = threading.Lock()
        self.name = name
        self.labels = message["labels"]
        self.metrics = defaultdict(float, message["metrics"])

    def format(self):
        lines = [f"# TYPE {self.name} {type(self).__name__.lower()}"]
        with self._lock:
            for k, v in self.metrics.items():
                labels = dict(zip(self.labels, k))
                lines.append(f"{self.name} {{{format_dict(labels)}}} {v}")
        return "\n".join(lines)


class Counter(PrometheusStat):
    def update(self, message):
        with self._lock:
            for k, v in message["metrics"].items():
                self.metrics[k] += v


class Gauge(PrometheusStat):
    def update(self, message):
        with self._lock:
            for k, v in message["metrics"].items():
                self.metrics[k] = v


class Histogram:
    def __init__(self, name, message):
        self._lock = threading.Lock()
        self.name = name
        self.labels = message["labels"]
        self.bins = message["bins"]
        self.bin_counts = defaultdict(
            lambda: [0] * len(self.bins),
            {k: list(v) for k, v in message["bin_counts"].items()},
        )
        self.sums = defaultdict(float, message["sums"])
        self.total_counts = defaultdict(int, message["total_counts"])

    def update(self, message):
        with self._lock:
            for k, v in message["total_counts"].items():
                self.total_counts[k] += v
            for k, v in message["sums"].items():
                self.sums[k] += v
            for k, v in message["bin_counts"].items():
                bin_counts = self.bin_counts[k]
                for i, count in enumerate(v):
                    bin_counts[i] += count

    def format(self):
        lines = [f"# TYPE {self.name} histogram"]
        with self._lock:
            for key in sorted(self.sums.keys()):
                bin_counts = self.bin_counts[key]
                message_sum = self.sums[key]
                total_count = self.total_counts[key]
                labels = format_dict(dict(zip(self.labels, key)))

                lines.extend(
                    f'{self.name}_bucket{{{labels},le="{bin_label:.6f}"}} {bin_count}'
                    for bin_label, bin_count in zip(self.bins, bin_counts)
                )
                lines.append(f'{self.name}_bucket{{{labels},le="+Inf"}} {total_count}')
                lines.append(f"{self.name}_sum{{{labels}}} {message_sum:.6f}")
                lines.append(f"{self.name}_count{{{labels}}} {total_count}")
        return "\n".join(lines)


STAT_TYPES = {"Counter": Counter, "Gauge": Gauge, "Histogram": Histogram}


class PrometheusMetrics:
    def __init__(self):
        self.stats = {}

    def process(self, msg):
        logger.debug(f"message to iterate in prometheus metrics: {msg}")
        for stat in msg:
            name = stat["name"]
            if name not in self.stats:
                self.stats[name] = STAT_TYPES[stat["type"]](name, stat)
            else:
                self.stats[name].update(stat)

    def format(self):
        blocks = [stat.format() for stat in self.stats.values()]
        return "\n\n".join(blocks)
