import unittest.mock as mock

import pytest

from mite.web.influxdb import InfluxMetrics, InfluxPoint, influxdb_init_points

TAGS = {"bar": "one", "baz": "two"}


def _counter(value):
    return {"type": "Counter", "name": "foo", "labels": ("bar", "baz"), "metrics": {("one", "two"): value}}


def _gauge(value):
    return {**_counter(value), "type": "Gauge"}


def _histogram():
    return {
        "type": "Histogram",
        "name": "foo",
        "labels": ("bar", "baz"),
        "bin_counts": {("one", "two"): (0, 1, 1)},
        "sums": {("one", "two"): 2},
        "total_counts": {("one", "two"): 1},
        "bins": (1, 2, 3),
    }


def _points_per_send(*dumps, include_buckets=False):
    """The points each send() produces, without writing them anywhere."""
    with mock.patch("mite.web.influxdb.time_ns", return_value=1), mock.patch.object(
        InfluxMetrics, "MIN_FLUSH_INTERVAL", 1e9
    ):
        metrics = InfluxMetrics(mock.Mock(), include_buckets=include_buckets)
        result = []
        for dump in dumps:
            before = len(metrics._pending_points)
            metrics.send(dump)
            result.append(metrics._pending_points[before:])
    return result


class TestCounter:
    def test_value_is_the_change_and_value_cumulative_the_total(self):
        first, second = _points_per_send([_counter(1)], [_counter(3)])
        assert first == [InfluxPoint("foo", TAGS, {"value": 1, "value_cumulative": 1}, 1)]
        assert second == [InfluxPoint("foo", TAGS, {"value": 3, "value_cumulative": 4}, 1)]

    def test_only_stats_in_the_dump_are_written(self):
        _, second = _points_per_send([_counter(1)], [{**_counter(1), "metrics": {}}])
        assert second == []


class TestGauge:
    def test_value_is_the_latest(self):
        first, second = _points_per_send([_gauge(1)], [_gauge(5)])
        assert first == [InfluxPoint("foo", TAGS, {"value": 1.0}, 1)]
        assert second == [InfluxPoint("foo", TAGS, {"value": 5.0}, 1)]


class TestHistogram:
    def test_change_and_cumulative_fields(self):
        first, second = _points_per_send([_histogram()], [_histogram()])
        (point,) = second
        assert point.measurement == "foo_summary"
        assert point.tags == TAGS
        assert point.fields["count"] == 1
        assert point.fields["count_cumulative"] == 2
        assert point.fields["sum"] == pytest.approx(2.0)
        assert point.fields["sum_cumulative"] == pytest.approx(4.0)
        assert point.fields["avg"] == pytest.approx(2.0)
        assert point.fields["p50"] == pytest.approx(1.5)
        assert point.fields["p50_cumulative"] == pytest.approx(1.5)
        assert first[0].fields["count_cumulative"] == 1

    def test_buckets_are_cumulative(self):
        _, second = _points_per_send([_histogram()], [_histogram()], include_buckets=True)
        buckets = {p.tags["le"]: p.fields["count"] for p in second if p.measurement == "foo_bucket"}
        assert buckets == {"1": 0, "2": 2, "3": 2, "+Inf": 2}


def test_unknown_stat_type_is_skipped_and_logged_once():
    unknown = {"type": "Summary", "name": "odd", "labels": (), "metrics": {}}
    with mock.patch("mite.web.totals.logger.error") as logging_error:
        first, second = _points_per_send([unknown, _counter(1)], [unknown, _counter(1)])
    assert [p.measurement for p in first + second] == ["foo", "foo"]
    logging_error.assert_called_once()
    assert "odd" in logging_error.call_args[0][1]


def test_init_points_use_the_same_fields_as_real_data():
    dumps = [
        {**_counter(0), "metrics": {}},
        {**_gauge(0), "name": "g", "metrics": {}},
        {**_histogram(), "name": "h", "bin_counts": {}, "sums": {}, "total_counts": {}},
    ]
    points = {p.measurement: p for p in influxdb_init_points(dumps, 7)}
    assert points["foo"] == InfluxPoint("foo", {"bar": "__init__", "baz": "__init__"}, {"value": 0, "value_cumulative": 0}, 7)
    assert points["g"].fields == {"value": 0.0}
    (real,) = _points_per_send([{**_histogram(), "name": "h"}])[0]
    assert set(points["h_summary"].fields) == set(real.fields)
    assert all(v == 0 for v in points["h_summary"].fields.values())
