import copy
import importlib
import unittest.mock as mock
import warnings

import pytest

from mite.stats import (
    Counter,
    Extractor,
    Gauge,
    Histogram,
    Stats,
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
        return [self.__val]


class TestModularity:
    def test_modularity(self):
        with mock.patch(
            "mite.stats.logger.info"
        ) as logging_info, mock.patch(
            "importlib.metadata.entry_points", return_value=[EntryPointMock(group="x")]
        ) as iter_entry_points:
            s = Stats(None)
            iter_entry_points.assert_called_once()
            logging_info.assert_called_with("Registering stats processors from x")
            assert s._all_stats == ["x"]

    def test_modularity_include(self):
        with mock.patch(
            "importlib.metadata.entry_points",
            return_value=[EntryPointMock(group="x"), EntryPointMock(group="y")],
        ):
            s = Stats(None, include=["x"])
            assert s._all_stats == ["x"]

    def test_modularity_exclude(self):
        with mock.patch(
            "importlib.metadata.entry_points",
            return_value=[EntryPointMock(group="x"), EntryPointMock(group="y")],
        ):
            s = Stats(None, exclude=["x"])
            assert s._all_stats == ["y"]

    def _entry_points_with_opt_in(self):
        return [EntryPointMock(group="x"), EntryPointMock(group="mite_http_extended")]

    def test_opt_in_processor_excluded_by_default(self):
        with mock.patch(
            "importlib.metadata.entry_points", return_value=self._entry_points_with_opt_in()
        ):
            assert Stats(None)._all_stats == ["x"]
            assert Stats(None, exclude=["y"])._all_stats == ["x"]

    def test_opt_in_processor_included_by_name(self):
        with mock.patch(
            "importlib.metadata.entry_points", return_value=self._entry_points_with_opt_in()
        ):
            s = Stats(None, include=["mite_http_extended"])
            assert s._all_stats == ["mite_http_extended"]
            s = Stats(None, include=["x", "mite_http_extended"])
            assert s._all_stats == ["x", "mite_http_extended"]

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
            s = Stats(None)
            assert s._all_stats == ["y"]
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
            s = Stats(None)
            assert s._all_stats == ["y"]
            logging_error.assert_called_once()
            assert "mite_amqp" in logging_error.call_args[0][0]

    def test_future_warning_from_a_loaded_processor_does_not_escape(self):
        def _warn_and_return():
            warnings.warn("some mite 4.0 deprecation", FutureWarning, stacklevel=2)
            return ["x"]

        with mock.patch(
            "importlib.metadata.entry_points",
            return_value=[EntryPointMock(group="x")],
        ) as iter_entry_points:
            iter_entry_points.return_value[0].load = _warn_and_return
            with warnings.catch_warnings(record=True) as record:
                warnings.simplefilter("always")
                s = Stats(None)
            future_warnings = [
                w for w in record if issubclass(w.category, FutureWarning)
            ]
            assert not future_warnings, future_warnings
            assert s._all_stats == ["x"]

    def test_first_party_stats_actually_load(self):
        # Unpatched: exercises the real entry points registered in
        # pyproject.toml for mite's own stats processors.
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            s = Stats(None)
        future_warnings = [w for w in record if issubclass(w.category, FutureWarning)]
        assert not future_warnings, future_warnings
        names = [stat.name for stat in s._all_stats]
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
        counter = Counter("test", lambda x: True, self.dummy_extractor)
        counter.process(None)
        assert dict(counter.metrics) == {"foo": 1}

    def test_process_additivity(self):
        counter = Counter("test", lambda x: True, self.dummy_extractor)
        counter.process(None)
        counter.process(None)
        assert dict(counter.metrics) == {"foo": 2}

    def test_dump(self):
        counter = Counter("test", lambda x: True, self.dummy_extractor)
        counter.process(None)
        assert counter.dump() == {
            "type": "Counter",
            "name": "test",
            "metrics": {"foo": 1},
            "labels": ("bar",),
        }
        assert dict(counter.metrics) == {}

    def test_process_after_dump(self):
        counter = Counter("test", lambda x: True, self.dummy_extractor)
        counter.process(None)
        counter.dump()
        counter.process(None)
        assert dict(counter.metrics) == {"foo": 1}


class TestGauge:
    dummy_extractor = Extractor(labels=("bar",), extract=lambda x: (("foo", 3),))

    def test_process(self):
        gauge = Gauge("test", lambda x: True, self.dummy_extractor)
        gauge.process(None)
        assert dict(gauge.metrics) == {"foo": 3.0}

    def test_process_non_additivity(self):
        gauge = Gauge("test", lambda x: True, self.dummy_extractor)
        gauge.process(None)
        gauge.process(None)
        assert dict(gauge.metrics) == {"foo": 3.0}

    def test_dump(self):
        gauge = Gauge("test", lambda x: True, self.dummy_extractor)
        gauge.process(None)
        assert gauge.dump() == {
            "type": "Gauge",
            "name": "test",
            "metrics": {"foo": 3.0},
            "labels": ("bar",),
        }
        assert dict(gauge.metrics) == {}

    def test_process_after_dump(self):
        gauge = Gauge("test", lambda x: True, self.dummy_extractor)
        gauge.process(None)
        gauge.dump()
        gauge.process(None)
        assert dict(gauge.metrics) == {"foo": 3.0}


class TestHistogram:
    dummy_extractor = Extractor(labels=("bar",), extract=lambda x: (("foo", 3),))

    def test_process(self):
        hist = Histogram("test", lambda _: True, self.dummy_extractor, (1, 2, 3, 4))
        hist.process(None)
        assert dict(hist.bin_counts) == {"foo": [0, 0, 1, 1]}
        assert dict(hist.sums) == {"foo": 3}
        assert dict(hist.total_counts) == {"foo": 1}

    def test_process_additivity(self):
        hist = Histogram("test", lambda _: True, self.dummy_extractor, (1, 2, 3, 4))
        hist.process(None)
        hist.process(None)
        assert dict(hist.bin_counts) == {"foo": [0, 0, 2, 2]}
        assert dict(hist.sums) == {"foo": 6}
        assert dict(hist.total_counts) == {"foo": 2}

    def test_dump(self):
        hist = Histogram("test", lambda _: True, self.dummy_extractor, (1, 2, 3, 4))
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
        hist = Histogram("test", lambda _: True, self.dummy_extractor, (1, 2, 3, 4))
        hist.process(None)
        hist.dump()
        hist.process(None)
        assert dict(hist.bin_counts) == {"foo": [0, 0, 1, 1]}
        assert dict(hist.sums) == {"foo": 3}
        assert dict(hist.total_counts) == {"foo": 1}


class _Uncopyable:
    def __deepcopy__(self, memo):
        raise TypeError("cannot copy me")


class _EntryPointFor:
    def __init__(self, name, stats):
        self.name = name
        self._stats = stats

    def load(self):
        return self._stats


def _counter(name):
    return Counter(name, lambda m: True, extractor(["test"]))


class TestCopyIsolation:
    def _entry_points(self):
        good1 = [_counter("a")]
        bad = [_counter("bad"), _Uncopyable()]
        good2 = [_counter("c")]
        eps = [
            _EntryPointFor("good1", good1),
            _EntryPointFor("failing", bad),
            _EntryPointFor("good2", good2),
        ]
        return eps, good1, bad, good2

    def test_copy_failure_skips_only_failing_plugin(self):
        eps, good1, _, good2 = self._entry_points()
        with mock.patch("mite.stats.logger") as logger, mock.patch(
            "importlib.metadata.entry_points", return_value=eps
        ):
            s = Stats(sender=lambda d: None)
        assert [st.name for st in s._all_stats] == ["a", "c"]
        assert s._all_stats[0] is not good1[0]
        assert s._all_stats[1] is not good2[0]
        logger.error.assert_called_once()
        message = logger.error.call_args[0][0]
        assert "failing" in message
        assert "cannot copy me" in message

    def test_default_loader_does_not_copy(self):
        eps, good1, bad, good2 = self._entry_points()
        with mock.patch("importlib.metadata.entry_points", return_value=eps):
            result = load_stats_entry_points()
        assert len(result) == 4
        assert result[0] is good1[0]
        assert result[1] is bad[0]
        assert result[2] is bad[1]
        assert result[3] is good2[0]


def test_histogram_copy_does_not_depend_on_original_bins():
    original = Histogram(
        "h", lambda m: True, Extractor(("bar",), lambda x: (("foo", 1),)), bins=[1, 2, 3]
    )
    clone = copy.deepcopy(original)
    original.bins.append(4)
    clone.process(None)
    assert dict(clone.bin_counts) == {"foo": [1, 1, 1]}


ALL_FIRST_PARTY = [
    "mite",
    "mite_finagle",
    "mite_http",
    "mite_http_extended",
    "mite_selenium",
    "mite_kafka",
    "mite_playwright",
]

_STATS_MODULES = {
    "mite": ("mite.stats", "_MITE_STATS"),
    "mite_finagle": ("mite_finagle.stats", "STATS"),
    "mite_http": ("mite_http.stats", "STATS"),
    "mite_http_extended": ("mite_http.stats", "EXTENDED_HTTP_STATS"),
    "mite_selenium": ("mite_selenium.stats", "STATS"),
    "mite_kafka": ("mite_kafka.stats", "_KAFKA_STATS"),
    "mite_playwright": ("mite_playwright.stats", "STATS"),
}

HTTP_MSG = {
    "type": "http_metrics",
    "test": "t",
    "journey": "j",
    "transaction": "txn_name",
    "method": "GET",
    "response_code": 200,
    "total_time": 0.05,
    "dns_time": 0.001,
    "connect_time": 0.002,
    "tls_time": 0.003,
    "transfer_start_time": 0.004,
    "posttransfer_time": 0.005,
    "first_byte_time": 0.006,
    "queue_time": 0.007,
    "client_lag": 0.008,
    "download_size": 1000,
    "upload_size": 500,
}


def _containers(stat):
    for attr in ("metrics", "bin_counts", "sums", "total_counts"):
        c = getattr(stat, attr, None)
        if c is not None:
            yield c


def _originals(names):
    originals = []
    for name in names:
        module_name, attr = _STATS_MODULES[name]
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        originals.extend(getattr(module, attr))
    return originals


def _by_position(dumps, stats):
    return {id(stat): dump for stat, dump in zip(stats, dumps)}


@pytest.mark.parametrize(
    "include",
    [None, ALL_FIRST_PARTY],
    ids=["default", "all_first_party_explicit"],
)
class TestRealEntryPointIsolation:
    def _build(self, include):
        sent = []
        s = Stats(sender=sent.append, include=include)
        return s, sent

    def test_isolation(self, include):
        s1, _ = self._build(include)
        s2, _ = self._build(include)
        if include is not None and len(s1._all_stats) == 0:
            pytest.skip("no first-party plugins installed")
        originals = _originals(include if include is not None else ["mite", "mite_finagle", "mite_http", "mite_selenium", "mite_kafka", "mite_playwright"])
        original_ids = {id(o) for o in originals}
        original_container_ids = {id(c) for o in originals for c in _containers(o)}
        assert len(s1._all_stats) == len(s2._all_stats)

        ids1 = {id(x) for st in s1._all_stats for x in (st, *_containers(st))}
        ids2 = {id(x) for st in s2._all_stats for x in (st, *_containers(st))}
        assert not ids1 & ids2
        assert not (ids1 | ids2) & (original_ids | original_container_ids)
        # Every stat object is distinct within an instance as well
        assert len({id(st) for st in s1._all_stats}) == len(s1._all_stats)

    def test_dumps_are_independent(self, include):
        s1, _ = self._build(include)
        s2, _ = self._build(include)
        names = [st.name for st in s1._all_stats]
        assert "mite_transaction_total" in names
        with_http = "mite_http_response_time_seconds" in names
        with_ext = "mite_http_dns_time_seconds" in names
        txn_idx = names.index("mite_transaction_total")

        def feed(s):
            s.process(TXN_MSG)
            if with_http:
                s.process(HTTP_MSG)

        with mock.patch("mite.stats.time") as t:
            t.time.return_value = 100.0
            s1.dump_timeout = s2.dump_timeout = 1000.0
            for cycle in range(2):
                feed(s1)
                feed(s2)
                d1 = s1.dump()
                d2 = s2.dump()
                for d in (d1, d2):
                    txn = d[txn_idx]
                    assert sum(txn["metrics"].values()) == 1
                    if with_http:
                        i = names.index("mite_http_response_time_seconds")
                        h = d[i]
                        assert h["total_counts"] == {("txn_name",): 1}
                        assert h["sums"] == {("txn_name",): 0.05}
                        counts = h["bin_counts"][("txn_name",)]
                        assert len(counts) == len(h["bins"])
                        assert counts == [1 if b >= 0.05 else 0 for b in h["bins"]]
                    if with_ext:
                        for stat_name in (
                            "mite_http_dns_time_seconds",
                            "mite_http_connect_time_seconds",
                            "mite_http_tls_time_seconds",
                            "mite_http_pretransfer_time_seconds",
                            "mite_http_posttransfer_time_seconds",
                            "mite_http_first_byte_time_seconds",
                            "mite_http_queue_time_seconds",
                            "mite_http_client_lag_seconds",
                            "mite_http_download_size_bytes",
                            "mite_http_upload_size_bytes",
                        ):
                            eh = d[names.index(stat_name)]
                            assert eh["total_counts"] == {("txn_name",): 1}, stat_name


class TestTwoInfluxDBProcessors:
    def test_two_processors_do_not_interfere(self):
        from mite.influxdb_processor import InfluxDBProcessor

        exporters = [mock.Mock(name="exp1"), mock.Mock(name="exp2")]
        with mock.patch("mite.stats.time") as t, mock.patch(
            "mite.web.influxdb.InfluxMetrics", side_effect=exporters
        ):
            t.time.return_value = 100.0
            procs = [
                InfluxDBProcessor({}, suffix=""),
                InfluxDBProcessor({}, suffix="_2"),
            ]
            for p in procs:
                p.process_message(TXN_MSG)
            for e in exporters:
                e.process.assert_not_called()

            t.time.return_value = 101.0
            for p in procs:
                p.process_message(TXN_MSG)

            labels = ("mite_project.file:scenario", "mite_project.file:journey", "txn_name", True)
            for e in exporters:
                e.process.assert_called_once()
                dumped = e.process.call_args[0][0]
                txn = next(d for d in dumped if d["name"] == "mite_transaction_total")
                assert txn["metrics"] == {labels: 2}

            # close() doesn't flush pending stats today; that is expected and
            # out of scope here.
            for p in procs:
                p.close()
            for e in exporters:
                e.close.assert_called_once()
