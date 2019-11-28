import logging
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)


def format_dict(d):
    return ','.join(
        [
            '%s="%s"' % (k, str(v).replace("\\", "\\\\").replace('"', '\\"'))
            for k, v in d.items()
        ]
    )


class PrometheusStat:
    def __init__(self, name, message):
        self._lock = threading.Lock()
        self.name = name
        self.labels = message['labels']
        self.metrics = defaultdict(float, message['metrics'])

    def format(self):
        lines = []
        lines.append(f"# TYPE {self.name} {type(self).__name__.lower()}")
        with self._lock:
            for k, v in self.metrics.items():
                labels = dict(zip(self.labels, k))
                lines.append("%s {%s} %s" % (self.name, format_dict(labels), v))
        return '\n'.join(lines)


class Counter(PrometheusStat):
    def update(self, message):
        with self._lock:
            for k, v in message['metrics'].items():
                self.metrics[k] += v


class Gauge(PrometheusStat):
    def update(self, message):
        with self._lock:
            for k, v in message['metrics'].items():
                self.metrics[k] = v


class Histogram:
    def __init__(self, name, message):
        self._lock = threading.Lock()
        self.name = name
        self.labels = message['labels']
        self.bins = message['bins']
        self.bin_counts = defaultdict(
            lambda: [0] * len(self.bins),
            {k: list(v) for k, v in message['bin_counts'].items()},
        )
        self.sums = defaultdict(float, message['sums'])
        self.total_counts = defaultdict(int, message['total_counts'])

    def update(self, message):
        with self._lock:
            for k, v in message['total_counts'].items():
                self.total_counts[k] += v
            for k, v in message['sums'].items():
                self.sums[k] += v
            for k, v in message['bin_counts'].items():
                bin_counts = self.bin_counts[k]
                for i, count in enumerate(v):
                    bin_counts[i] += count

    def format(self):
        lines = []
        lines.append('# TYPE %s histogram' % (self.name,))
        with self._lock:
            for key, bin_counts in sorted(self.bin_counts.items()):
                sum = self.sums[key]
                total_count = self.total_counts[key]
                labels = format_dict(dict(zip(self.labels, key)))
                for bin_label, bin_count in zip(self.bins, bin_counts):
                    lines.append(
                        '%s_bucket{%s,le="%.6f"} %d'
                        % (self.name, labels, bin_label, bin_count)
                    )
                lines.append(
                    '%s_bucket{%s,le="+Inf"} %d' % (self.name, labels, total_count)
                )
                lines.append('%s_sum{%s} %.6f' % (self.name, labels, sum))
                lines.append('%s_count{%s} %d' % (self.name, labels, total_count))
        return '\n'.join(lines)


STAT_TYPES = {'Counter': Counter, 'Gauge': Gauge, 'Histogram': Histogram}


class PrometheusMetrics:
    def __init__(self):
        self.stats = {}

    def process(self, msg):
        logger.debug("message to iterate in prometheus metrics: %s" % (msg,))
        for stat in msg:
            name = stat['name']
            if name not in self.stats:
                self.stats[name] = STAT_TYPES[stat['type']](name, stat)
            else:
                self.stats[name].update(stat)

    def format(self):
        blocks = []
        for stat in self.stats.values():
            blocks.append(stat.format())
        return '\n\n'.join(blocks)
