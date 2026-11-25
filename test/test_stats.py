import dataclasses
import unittest.mock as mock
import warnings

import pytest

from mite.stats import (
    Counter,
    Extractor,
    Gauge,
    GaugeAggregation,
    Histogram,
    Stat,
    Aggregator,
    extractor,
    load_stats_entry_points,
)

TXN_MSG = {
    "start_time": 1572604344.7903123,
    "end_time": 1572604346.0693598,
    "had_error": True,
    "type": "txn",
    "time": 1572604346.0693617,
    "test": "mite_project.file:scenario",
    "runner_id": 1,
    "journey": "mite_project.file:journey",
    "context_id": 8,
    "scenario_id": 31,
    "scenario_data_id": 2,
    "transaction": "txn_name",
    "transaction_id": 3,
}


def test_label_extractor_txn_msg():
    ex = extractor("test journey transaction had_error".split())
    ls = list(ex.extract(TXN_MSG))
    assert len(ls) == 1
    labels, _ = ls[0]
    expected_value = (
        "mite_project.file:scenario",
        "mite_project.file:journey",
        "txn_name",
        True,
    )
    assert tuple(labels) == expected_value


class EntryPointMock:
    def __init__(self, group="", raises=None):
        self.__val = group
        self._raises = raises

    @property
    def name(self):
        return self.__val

    def load(self):
        if self._raises is not None:
            raise self._raises
        return [_counter(self.__val)]


class TestModularity:
    def test_modularity(self):
        with mock.patch(
            "mite.stats.logger.info"
        ) as logging_info, mock.patch(
            "importlib.metadata.entry_points", return_value=[EntryPointMock(group="x")]
        ) as iter_entry_points:
            s = Aggregator([])
            iter_entry_points.assert_called_once()
            logging_info.assert_called_with("Registering stats processors from x")
            assert _names(s) == ["x"]

    def test_modularity_include(self):
        with mock.patch(
            "importlib.metadata.entry_points",
            return_value=[EntryPointMock(group="x"), EntryPointMock(group="y")],
        ):
            s = Aggregator([], include=["x"])
            assert _names(s) == ["x"]

    def test_modularity_exclude(self):
        with mock.patch(
            "importlib.metadata.entry_points",
            return_value=[EntryPointMock(group="x"), EntryPointMock(group="y")],
        ):
            s = Aggregator([], exclude=["x"])
            assert _names(s) == ["y"]

    def _entry_points_with_opt_in(self):
        return [EntryPointMock(group="x"), EntryPointMock(group="mite_http_extended")]

    def test_opt_in_processor_excluded_by_default(self):
        with mock.patch(
            "importlib.metadata.entry_points", return_value=self._entry_points_with_opt_in()
        ):
            assert _names(Aggregator([])) == ["x"]
            assert _names(Aggregator([], exclude=["y"])) == ["x"]

    def test_opt_in_processor_included_by_name(self):
        with mock.patch(
            "importlib.metadata.entry_points", return_value=self._entry_points_with_opt_in()
        ):
            s = Aggregator([], include=["mite_http_extended"])
            assert _names(s) == ["mite_http_extended"]
            s = Aggregator([], include=["x", "mite_http_extended"])
            assert _names(s) == ["x", "mite_http_extended"]

    def test_import_error_is_a_warning(self):
        with mock.patch(
            "mite.stats.logger.warning"
        ) as logging_warning, mock.patch(
            "importlib.metadata.entry_points",
            return_value=[
                EntryPointMock(
                    group="x",
                    raises=ModuleNotFoundError(
                        "mite_http requires the 'http' extra: pip install mite[http]"
                    ),
                ),
                EntryPointMock(group="y"),
            ],
        ):
            s = Aggregator([])
            assert _names(s) == ["y"]
            logging_warning.assert_called_once()
            message = logging_warning.call_args[0][0]
            assert "x" in message
            assert "pip install mite[http]" in message

    def test_other_exception_is_logged_not_raised(self):
        with mock.patch(
            "mite.stats.logger.error"
        ) as logging_error, mock.patch(
            "importlib.metadata.entry_points",
            return_value=[
                EntryPointMock(
                    group="mite_amqp",
                    raises=AttributeError("plugin bug"),
                ),
                EntryPointMock(group="y"),
            ],
        ):
            s = Aggregator([])
            assert _names(s) == ["y"]
            logging_error.assert_called_once()
            assert "mite_amqp" in logging_error.call_args[0][0]

    def test_future_warning_from_a_loaded_processor_does_not_escape(self):
        def _warn_and_return():
            warnings.warn("some mite 4.0 deprecation", FutureWarning, stacklevel=2)
            return [_counter("x")]

        with mock.patch(
            "importlib.metadata.entry_points",
            return_value=[EntryPointMock(group="x")],
        ) as iter_entry_points:
            iter_entry_points.return_value[0].load = _warn_and_return
            with warnings.catch_warnings(record=True) as record:
                warnings.simplefilter("always")
                s = Aggregator([])
            future_warnings = [
                w for w in record if issubclass(w.category, FutureWarning)
            ]
            assert not future_warnings, future_warnings
            assert _names(s) == ["x"]

    def test_first_party_stats_actually_load(self):
        # Unpatched: exercises the real entry points registered in
        # pyproject.toml for mite's own stats processors.
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            s = Aggregator([])
        future_warnings = [w for w in record if issubclass(w.category, FutureWarning)]
        assert not future_warnings, future_warnings
        names = _names(s)
        # mite_selenium_page_load_tcp_time_seconds appears twice due to a
        # pre-existing duplicate in mite_selenium/stats.py, unrelated to
        # this change - not asserted on beyond allowing it here.
        duplicates = {n for n in names if names.count(n) > 1}
        assert duplicates <= {"mite_selenium_page_load_tcp_time_seconds"}, duplicates
        for expected in (
            "mite_journey_error_total",  # mite's own _MITE_STATS
            "mite_http_response_total",
            "mite_kafka_producer_stats_counter",
            "mite_selenium_response_total",
            "mite_finagle_response_total",
        ):
            assert expected in names


class TestCounter:
    dummy_extractor = Extractor(labels=("bar",), extract=lambda x: (("foo", 1),))

    def test_process(self):
        counter = _aggregation(Counter("test", lambda x: True, self.dummy_extractor))
        counter.process(None)
        assert dict(counter.metrics) == {"foo": 1}

    def test_process_additivity(self):
        counter = _aggregation(Counter("test", lambda x: True, self.dummy_extractor))
        counter.process(None)
        counter.process(None)
        assert dict(counter.metrics) == {"foo": 2}

    def test_dump(self):
        counter = _aggregation(Counter("test", lambda x: True, self.dummy_extractor))
        counter.process(None)
        assert counter.dump() == {
            "type": "Counter",
            "name": "test",
            "metrics": {"foo": 1},
            "labels": ("bar",),
        }
        assert dict(counter.metrics) == {}

    def test_process_after_dump(self):
        counter = _aggregation(Counter("test", lambda x: True, self.dummy_extractor))
        counter.process(None)
        counter.dump()
        counter.process(None)
        assert dict(counter.metrics) == {"foo": 1}


class TestGauge:
    dummy_extractor = Extractor(labels=("bar",), extract=lambda x: (("foo", 3),))

    def test_process(self):
        gauge = _aggregation(Gauge("test", lambda x: True, self.dummy_extractor))
        gauge.process(None)
        assert dict(gauge.metrics) == {"foo": 3.0}

    def test_process_non_additivity(self):
        gauge = _aggregation(Gauge("test", lambda x: True, self.dummy_extractor))
        gauge.process(None)
        gauge.process(None)
        assert dict(gauge.metrics) == {"foo": 3.0}

    def test_dump(self):
        gauge = _aggregation(Gauge("test", lambda x: True, self.dummy_extractor))
        gauge.process(None)
        assert gauge.dump() == {
            "type": "Gauge",
            "name": "test",
            "metrics": {"foo": 3.0},
            "labels": ("bar",),
        }
        assert dict(gauge.metrics) == {}

    def test_process_after_dump(self):
        gauge = _aggregation(Gauge("test", lambda x: True, self.dummy_extractor))
        gauge.process(None)
        gauge.dump()
        gauge.process(None)
        assert dict(gauge.metrics) == {"foo": 3.0}


class TestHistogram:
    dummy_extractor = Extractor(labels=("bar",), extract=lambda x: (("foo", 3),))

    def test_process(self):
        hist = _aggregation(Histogram("test", lambda _: True, self.dummy_extractor, (1, 2, 3, 4)))
        hist.process(None)
        assert dict(hist.bin_counts) == {"foo": [0, 0, 1, 1]}
        assert dict(hist.sums) == {"foo": 3}
        assert dict(hist.total_counts) == {"foo": 1}

    def test_process_additivity(self):
        hist = _aggregation(Histogram("test", lambda _: True, self.dummy_extractor, (1, 2, 3, 4)))
        hist.process(None)
        hist.process(None)
        assert dict(hist.bin_counts) == {"foo": [0, 0, 2, 2]}
        assert dict(hist.sums) == {"foo": 6}
        assert dict(hist.total_counts) == {"foo": 2}

    def test_dump(self):
        hist = _aggregation(Histogram("test", lambda _: True, self.dummy_extractor, (1, 2, 3, 4)))
        hist.process(None)
        assert hist.dump() == {
            "type": "Histogram",
            "name": "test",
            "bin_counts": {"foo": [0, 0, 1, 1]},
            "sums": {"foo": 3},
            "total_counts": {"foo": 1},
            "bins": [1, 2, 3, 4],
            "labels": ("bar",),
        }
        assert dict(hist.total_counts) == {}
        assert dict(hist.sums) == {}
        assert dict(hist.bin_counts) == {}

    def test_process_after_dump(self):
        hist = _aggregation(Histogram("test", lambda _: True, self.dummy_extractor, (1, 2, 3, 4)))
        hist.process(None)
        hist.dump()
        hist.process(None)
        assert dict(hist.bin_counts) == {"foo": [0, 0, 1, 1]}
        assert dict(hist.sums) == {"foo": 3}
        assert dict(hist.total_counts) == {"foo": 1}


class _EntryPointFor:
    def __init__(self, name, stats):
        self.name = name
        self._stats = stats

    def load(self):
        return self._stats


def _counter(name):
    return Counter(name, lambda m: True, extractor(["test"]))


def _aggregation(stat):
    return stat.aggregation_class(stat)


def _names(aggregator):
    return [a.stat.name for a in aggregator._aggregations]


def test_stat_definitions_are_immutable():
    hist = Histogram("h", lambda m: True, extractor(["test"]), bins=[3, 1, 2])
    assert hist.bins == (1, 2, 3)
    with pytest.raises(dataclasses.FrozenInstanceError):
        hist.bins = (4,)


def test_two_aggregators_do_not_share_state():
    # Regression for --influxdb=2: entry_point.load() returns the plugin's
    # module-level STATS list, so every aggregator sees the same definitions.
    # Each must keep its own counts, or messages are double-counted and one
    # aggregator's dump() clears the other's pending data.
    with mock.patch(
        "importlib.metadata.entry_points",
        return_value=[_EntryPointFor("x", [_counter("mite_transaction_total")])],
    ):
        s1 = Aggregator([])
        s2 = Aggregator([])

    assert s1._aggregations[0].stat is s2._aggregations[0].stat
    assert s1._aggregations[0] is not s2._aggregations[0]

    s1.process(TXN_MSG)
    d1 = s1.dump()
    d2 = s2.dump()
    assert sum(d1[0]["metrics"].values()) == 1
    assert sum(d2[0]["metrics"].values()) == 0


def test_entry_point_exporting_non_stats_is_logged_and_skipped():
    with mock.patch("mite.stats.logger.error") as logging_error, mock.patch(
        "importlib.metadata.entry_points",
        return_value=[
            _EntryPointFor("bad", [_counter("ok"), "not a stat"]),
            _EntryPointFor("good", [_counter("y")]),
        ],
    ):
        stats = load_stats_entry_points()
    assert [s.name for s in stats] == ["y"]
    logging_error.assert_called_once()
    assert "bad" in logging_error.call_args[0][0]
    assert "not a stat" in logging_error.call_args[0][0]


class _MaxGaugeAggregation(GaugeAggregation):
    def process(self, msg):
        if self.stat.matcher(msg):
            for key, value in self.stat.extractor.extract(msg):
                self.metrics[key] = max(value, self.metrics.get(key, value))


@dataclasses.dataclass(frozen=True)
class _MaxGauge(Stat):
    aggregation_class = _MaxGaugeAggregation


def test_custom_stat_type_is_aggregated():
    stat = _MaxGauge("peak", lambda m: True, extractor(["test"], "value"))
    with mock.patch(
        "importlib.metadata.entry_points",
        return_value=[_EntryPointFor("custom", [stat])],
    ):
        aggregator = Aggregator([])
    for value in (3, 7, 5):
        aggregator.process({"test": "t", "value": value})
    assert aggregator.dump() == [
        {"type": "Gauge", "name": "peak", "metrics": {("t",): 7}, "labels": ["test"]}
    ]


def test_stat_without_aggregation_class_is_logged_and_skipped():
    with mock.patch("mite.stats.logger.error") as logging_error, mock.patch(
        "importlib.metadata.entry_points",
        return_value=[_EntryPointFor("bad", [Stat("x", lambda m: True, extractor(["test"]))])],
    ):
        assert load_stats_entry_points() == []
    assert "aggregation_class" in logging_error.call_args[0][0]


def _aggregator_with_counter(senders):
    with mock.patch(
        "importlib.metadata.entry_points",
        return_value=[_EntryPointFor("x", [_counter("mite_transaction_total")])],
    ):
        return Aggregator(senders)


def _txn_total(dump):
    return sum(dump[0]["metrics"].values())


class TestAggregatorSenders:
    def test_each_sender_gets_each_dump_once(self):
        senders = [mock.Mock(), mock.Mock()]
        aggregator = _aggregator_with_counter(senders)
        aggregator.process(TXN_MSG)
        aggregator.flush()
        for sender in senders:
            sender.send.assert_called_once()
            assert _txn_total(sender.send.call_args[0][0]) == 1

    def test_process_flushes_after_the_dump_interval(self):
        sender = mock.Mock()
        with mock.patch("mite.stats.time") as t:
            t.time.return_value = 100.0
            aggregator = _aggregator_with_counter([sender])
            aggregator.process(TXN_MSG)
            sender.send.assert_not_called()
            t.time.return_value = 100.3
            aggregator.process(TXN_MSG)
        assert _txn_total(sender.send.call_args[0][0]) == 2

    def test_close_sends_pending_stats_then_closes(self):
        # Before 4.0 the counts since the last 0.25s dump were lost at the end
        # of a test run (fix first proposed by Davide in stats-influx-close-flush)
        sender = mock.Mock()
        with mock.patch("mite.stats.time") as t:
            t.time.return_value = 100.0
            aggregator = _aggregator_with_counter([sender])
            aggregator.process(TXN_MSG)
        sender.send.assert_not_called()

        aggregator.close()

        assert _txn_total(sender.send.call_args[0][0]) == 1
        sender.close.assert_called_once()

    def test_failing_sender_does_not_stop_the_others(self):
        failing, working = mock.Mock(), mock.Mock()
        failing.send.side_effect = RuntimeError("boom")
        aggregator = _aggregator_with_counter([failing, working])
        aggregator.process(TXN_MSG)
        with mock.patch("mite.stats.logger.exception") as logging_exception:
            aggregator.flush()
        logging_exception.assert_called_once()
        assert _txn_total(working.send.call_args[0][0]) == 1

    def test_close_closes_every_sender_then_raises_the_first_failure(self):
        failing, working = mock.Mock(), mock.Mock()
        failing.close.side_effect = RuntimeError("boom")
        aggregator = _aggregator_with_counter([failing, working])
        with pytest.raises(RuntimeError, match="boom"):
            aggregator.close()
        working.close.assert_called_once()
