"""Running totals of aggregator dumps, shared by the stats outputs.

An :class:`mite.stats.Aggregator` dump holds what changed since the previous
dump. Prometheus reports totals since the start of the run, and InfluxDB
writes both the change and the total, so both build on :class:`RunningTotals`.
"""

import logging
import threading

logger = logging.getLogger(__name__)


class CounterTotals:
    def __init__(self, summary):
        self.name = summary["name"]
        self.labels = summary["labels"]
        self.values = {}

    def update(self, summary):
        for key, value in summary["metrics"].items():
            self.values[key] = self.values.get(key, 0) + value


class GaugeTotals(CounterTotals):
    def update(self, summary):
        self.values.update(summary["metrics"])


class HistogramTotals:
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
            totals = self.bin_counts.setdefault(key, [0] * len(self.bins))
            for i, count in enumerate(counts):
                totals[i] += count


TOTALS_TYPES = {
    "Counter": CounterTotals,
    "Gauge": GaugeTotals,
    "Histogram": HistogramTotals,
}


class RunningTotals:
    """Totals per stat across every dump given to :meth:`update`.

    Hold :attr:`lock` while reading the totals from another thread.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.stats = {}
        self._skipped = set()

    def update(self, dump):
        """Add a dump to the totals. Returns a ``(totals, summary)`` pair for
        each stat in the dump, so outputs can use both the change and the
        total. Stats with an unknown ``"type"`` are skipped, with an error
        logged once per stat."""
        updated = []
        with self.lock:
            for summary in dump:
                totals = self.stats.get(summary["name"])
                if totals is None:
                    totals_type = TOTALS_TYPES.get(summary["type"])
                    if totals_type is None:
                        self._skip(summary)
                        continue
                    totals = self.stats[summary["name"]] = totals_type(summary)
                totals.update(summary)
                updated.append((totals, summary))
        return updated

    def _skip(self, summary):
        if summary["name"] not in self._skipped:
            self._skipped.add(summary["name"])
            logger.error(
                "Skipping stat %s: unknown type %r; expected one of %s",
                summary["name"],
                summary["type"],
                ", ".join(TOTALS_TYPES),
            )
