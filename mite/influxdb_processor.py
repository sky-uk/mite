import logging

from .stats import Stats

logger = logging.getLogger(__name__)


class InfluxDBProcessor:
    def __init__(self, opts, suffix=""):
        # Deferred, not module-level - mite/cli/test.py imports
        # InfluxDBProcessor unconditionally (used only when --influxdb is
        # passed), and mite.web.influxdb pulls in flask via
        # mite/web/__init__.py's own import chain. A module-level import
        # here would make every mite scenario/journey test process pay that
        # cost whether or not --influxdb was requested.
        from .web.influxdb import InfluxMetrics

        include_buckets = opts.get("--include-buckets", False)
        self._influx_metrics = InfluxMetrics(include_buckets=include_buckets, suffix=suffix)
        # Stats aggregator - instead of sending to socket, we'll capture dumps
        self._stats = Stats(sender=self._on_stats_dump)

    def _on_stats_dump(self, dumped_stats):
        self._influx_metrics.process(dumped_stats)

    def process_message(self, msg):
        self._stats.process(msg)

    def close(self):
        self._influx_metrics.close()
