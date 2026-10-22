import logging
import unittest.mock as mock
import warnings

import pytest

from mite.stats import Counter, Extractor, Gauge, Histogram, Stats, extractor

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


# Every TestModularity test patches mite.stats._FIRST_PARTY_STATS to {}
# (unless it's specifically testing first-party loading) so these tests
# exercise only the entry-point scanning side, undisturbed by whatever
# mite's own six processors happen to do at the time.
class TestModularity:
    def test_modularity(self):
        with mock.patch("mite.stats._FIRST_PARTY_STATS", {}), mock.patch(
            "mite.stats.logger.info"
        ) as logging_info, mock.patch(
            "importlib.metadata.entry_points", return_value=[EntryPointMock(group="x")]
        ) as iter_entry_points:
            s = Stats(None)
            iter_entry_points.assert_called_once()
            logging_info.assert_called_with("Registering stats processors from x")
            assert s._all_stats == ["x"]

    def test_modularity_include(self):
        with mock.patch("mite.stats._FIRST_PARTY_STATS", {}), mock.patch(
            "importlib.metadata.entry_points",
            return_value=[EntryPointMock(group="x"), EntryPointMock(group="y")],
        ):
            s = Stats(None, include=["x"])
            assert s._all_stats == ["x"]

    def test_modularity_exclude(self):
        with mock.patch("mite.stats._FIRST_PARTY_STATS", {}), mock.patch(
            "importlib.metadata.entry_points",
            return_value=[EntryPointMock(group="x"), EntryPointMock(group="y")],
        ):
            s = Stats(None, exclude=["x"])
            assert s._all_stats == ["y"]

    def test_first_party_loaded_from_registry_not_entry_points(self):
        """mite's own stats load via _FIRST_PARTY_STATS's "module:attr"
        spec, resolved by _load_spec - not via importlib.metadata at all."""
        with mock.patch(
            "mite.stats._FIRST_PARTY_STATS", {"mock_stat": "mocks.mock_stats:STATS"}
        ), mock.patch(
            "importlib.metadata.entry_points", return_value=[]
        ) as iter_entry_points:
            s = Stats(None)
            assert s._all_stats == ["mock_stat"]
            iter_entry_points.assert_called_once()

    def test_entry_point_colliding_with_reserved_name_is_skipped(self):
        with mock.patch(
            "mite.stats._FIRST_PARTY_STATS", {"mite_http": "mocks.mock_stats:STATS"}
        ), mock.patch("mite.stats.logger.warning") as logging_warning, mock.patch(
            "importlib.metadata.entry_points",
            return_value=[EntryPointMock(group="mite_http"), EntryPointMock(group="y")],
        ):
            s = Stats(None)
            # The reserved-name entry point is skipped, not loaded alongside
            # the first-party one - otherwise mock_stats.STATS would appear
            # twice in _all_stats.
            assert s._all_stats == ["mock_stat", "y"]
            logging_warning.assert_called_once()
            assert "mite_http" in logging_warning.call_args[0][0]

    def test_first_party_import_error_is_a_warning(self):
        with mock.patch("mite.stats._FIRST_PARTY_STATS", {}), mock.patch(
            "mite.stats.logger.log"
        ) as logging_log, mock.patch(
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
            logging_log.assert_called_once()
            level, message = logging_log.call_args[0]
            assert level == logging.WARNING
            assert "x" in message
            assert "pip install mite[http]" in message

    def test_import_error_for_an_expected_absence_is_a_debug_log(self):
        """mite_playwright isn't part of mite's default install (see
        pyproject.toml), so a missing dependency for it specifically is
        expected, not worth warning about."""
        with mock.patch(
            "mite.stats._FIRST_PARTY_STATS", {"mite_playwright": "does.not:exist"}
        ), mock.patch("mite.stats.logger.log") as logging_log, mock.patch(
            "importlib.metadata.entry_points", return_value=[]
        ):
            s = Stats(None)
            assert s._all_stats == []
            logging_log.assert_called_once()
            level, message = logging_log.call_args[0]
            assert level == logging.DEBUG
            assert "mite_playwright" in message

    def test_first_party_other_exception_is_raised(self):
        with mock.patch("mite.stats._FIRST_PARTY_STATS", {}), mock.patch(
            "mite.stats._iter_stats_sources",
            return_value=[("x", mock.Mock(side_effect=AttributeError("real bug")), True)],
        ):
            with pytest.raises(AttributeError, match="real bug"):
                Stats(None)

    def test_third_party_any_exception_is_logged_not_raised(self):
        with mock.patch("mite.stats._FIRST_PARTY_STATS", {}), mock.patch(
            "mite.stats.logger.error"
        ) as logging_error, mock.patch(
            "importlib.metadata.entry_points",
            return_value=[
                EntryPointMock(
                    group="mite_amqp",
                    raises=AttributeError("third-party plugin bug"),
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
            warnings.warn("some mite 3.0 deprecation", FutureWarning, stacklevel=2)
            return ["x"]

        with mock.patch("mite.stats._FIRST_PARTY_STATS", {}), mock.patch(
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
        """Unpatched - exercises the real _FIRST_PARTY_STATS specs, not a
        mock standing in for them. Guards against the specs drifting from
        a future mite_*/stats.py rename or move - a mismatch here is a
        silent "this integration's metrics are never aggregated", not an
        import error, since load_stats_entry_points() treats a missing
        stats source as indistinguishable from a legitimately absent one.

        mite_playwright is deliberately not asserted on: playwright isn't
        part of the default install (see pyproject.toml), so its absence
        here is expected, not a regression - see _ABSENCE_EXPECTED."""
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            s = Stats(None)
        future_warnings = [w for w in record if issubclass(w.category, FutureWarning)]
        assert not future_warnings, future_warnings
        names = [stat.name for stat in s._all_stats]
        # mite_selenium_page_load_tcp_time_seconds appears twice: a
        # pre-existing duplicate entry in mite_selenium/stats.py's
        # _PAGE_LOAD_METRICS list, unrelated to this change - not asserting
        # full uniqueness here so this test doesn't mask that separately
        # reported bug, but still asserting no *entry point* produced a
        # duplicate (which is what this change could plausibly break).
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
