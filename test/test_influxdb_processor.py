import unittest.mock as mock

import pytest

from mite.influxdb_processor import InfluxDBProcessor
from mite.stats import Counter, extractor

TXN_MSG = {
    "type": "txn",
    "test": "mite_project.file:scenario",
    "journey": "mite_project.file:journey",
    "transaction": "txn_name",
    "had_error": False,
}


class _EntryPointFor:
    def __init__(self, name, stats):
        self.name = name
        self._stats = stats

    def load(self):
        return self._stats


def _entry_points():
    return [
        _EntryPointFor(
            "mite",
            [
                Counter(
                    "mite_transaction_total",
                    lambda m: m.get("type") == "txn",
                    extractor("test journey transaction had_error".split()),
                )
            ],
        )
    ]


class TestInfluxDBProcessorClose:
    def _build(self):
        with mock.patch(
            "importlib.metadata.entry_points", return_value=_entry_points()
        ), mock.patch("mite.web.influxdb.InfluxMetrics") as influx_metrics_cls:
            influx_metrics = influx_metrics_cls.return_value
            processor = InfluxDBProcessor({}, suffix="")
        return processor, influx_metrics

    def test_close_flushes_pending_stats(self):
        # Frozen clock: dump_timeout is never reached, so nothing is sent
        # until close().
        with mock.patch("mite.stats.time") as t:
            t.time.return_value = 100.0
            processor, influx_metrics = self._build()
            processor.process_message(TXN_MSG)
        influx_metrics.process.assert_not_called()

        processor.close()

        influx_metrics.process.assert_called_once()
        dumped = influx_metrics.process.call_args[0][0]
        txn = next(d for d in dumped if d["name"] == "mite_transaction_total")
        assert sum(txn["metrics"].values()) == 1
        influx_metrics.close.assert_called_once()

    def test_close_still_closes_influx_metrics_if_dump_processing_fails(self):
        processor, influx_metrics = self._build()
        influx_metrics.process.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            processor.close()

        influx_metrics.close.assert_called_once()
