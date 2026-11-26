"""Cumulative values of aggregator dumps, shared by the stats outputs.

An :class:`mite.stats.Aggregator` dump holds what changed since the previous
dump. Prometheus reports values since the start of the run, and InfluxDB writes
both the change and the cumulative value, so both build on
:class:`CumulativeStats`: counter and histogram values are summed across dumps,
and gauges keep their latest value.
"""

import logging
import threading

logger = logging.getLogger(__name__)


class CumulativeCounter:
    def __init__(self, summary):
        self.name = summary["name"]
        self.labels = summary["labels"]
        self.values = {}

    def update(self, summary):
        for key, value in summary["metrics"].items():
            self.values[key] = self.values.get(key, 0) + value


class CumulativeGauge(CumulativeCounter):
    def update(self, summary):
        self.values.update(summary["metrics"])


class CumulativeHistogram:
    def __init__(self, summary):
        self.name = summary["name"]
        self.labels = summary["labels"]
        self.bins = tuple(summary["bins"])
        self.bin_counts = {}
        self.sums = {}
        self.total_counts = {}

    def update(self, summary):
        for key, value in summary["total_counts"].items():
            self.total_counts[key] = self.total_counts.get(key, 0) + value
        for key, value in summary["sums"].items():
            self.sums[key] = self.sums.get(key, 0) + value
        for key, counts in summary["bin_counts"].items():
            bin_counts = self.bin_counts.setdefault(key, [0] * len(self.bins))
            for i, count in enumerate(counts):
                bin_counts[i] += count


CUMULATIVE_TYPES = {
    "Counter": CumulativeCounter,
    "Gauge": CumulativeGauge,
    "Histogram": CumulativeHistogram,
}


class CumulativeStats:
    """Cumulative values per stat across every dump given to :meth:`update`.

    Hold :attr:`lock` while reading the values from another thread.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.stats = {}
        self._skipped = set()

    def update(self, dump):
        """Add a dump to the cumulative values. Returns a ``(cumulative,
        summary)`` pair for each stat in the dump, so outputs can use both the
        cumulative value and the change. Stats with an unknown ``"type"`` are skipped, with an error
        logged once per stat."""
        updated = []
        with self.lock:
            for summary in dump:
                cumulative = self.stats.get(summary["name"])
                if cumulative is None:
                    cumulative_type = CUMULATIVE_TYPES.get(summary["type"])
                    if cumulative_type is None:
                        self._skip(summary)
                        continue
                    cumulative = self.stats[summary["name"]] = cumulative_type(summary)
                cumulative.update(summary)
                updated.append((cumulative, summary))
        return updated

    def _skip(self, summary):
        if summary["name"] not in self._skipped:
            self._skipped.add(summary["name"])
            logger.error(
                "Skipping stat %s: unknown type %r; expected one of %s",
                summary["name"],
                summary["type"],
                ", ".join(CUMULATIVE_TYPES),
            )
