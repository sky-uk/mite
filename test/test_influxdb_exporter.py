import pytest

from mite.web.influxdb import InfluxCounter, InfluxGauge, InfluxHistogram, InfluxPoint


class TestInfluxCounter:
    def test_counter_to_points(self):
        test_message = {
            "name": "foo",
            "labels": ("bar", "baz"),
            "metrics": {("one", "two"): 1},
        }
        c = InfluxCounter("foo", test_message)
        points = c.to_points(time_ns=1)
        assert points == [
            InfluxPoint(
                measurement="foo",
                tags={"bar": "one", "baz": "two"},
                fields={"value": 1, "value_cumulative": 1},
                time_ns=1,
            )
        ]

    def test_counter_update(self):
        test_message = {
            "name": "foo",
            "labels": ("bar", "baz"),
            "metrics": {("one", "two"): 1},
        }
        c = InfluxCounter("foo", test_message)
        c.to_points(time_ns=1)  # establish baseline for delta calculation
        c.update(test_message)
        points = c.to_points(time_ns=2)
        assert points == [
            InfluxPoint(
                measurement="foo",
                tags={"bar": "one", "baz": "two"},
                fields={"value": 1, "value_cumulative": 2},
                time_ns=2,
            )
        ]


class TestInfluxGauge:
    def test_gauge_to_points(self):
        test_message = {
            "name": "foo",
            "labels": ("bar", "baz"),
            "metrics": {("one", "two"): 1},
        }
        g = InfluxGauge("foo", test_message)
        points = g.to_points(time_ns=1)
        assert points == [
            InfluxPoint(
                measurement="foo",
                tags={"bar": "one", "baz": "two"},
                fields={"value": 1.0},
                time_ns=1,
            )
        ]

    def test_gauge_update(self):
        test_message = {
            "name": "foo",
            "labels": ("bar", "baz"),
            "metrics": {("one", "two"): 1},
        }
        g = InfluxGauge("foo", test_message)
        g.update({"metrics": {("one", "two"): 5}})
        points = g.to_points(time_ns=2)
        assert points == [
            InfluxPoint(
                measurement="foo",
                tags={"bar": "one", "baz": "two"},
                fields={"value": 5.0},
                time_ns=2,
            )
        ]


class TestInfluxHistogram:
    def test_histogram_to_points(self):
        test_message = {
            "name": "foo",
            "labels": ("bar", "baz"),
            "bin_counts": {("one", "two"): (0, 1, 1)},
            "sums": {("one", "two"): 2},
            "total_counts": {("one", "two"): 1},
            "bins": (1, 2, 3),
        }
        h = InfluxHistogram("foo", test_message)
        points = h.to_points(time_ns=1)
        assert len(points) == 1
        point = points[0]
        assert point.measurement == "foo_summary"
        assert point.tags == {"bar": "one", "baz": "two"}
        assert point.fields["count"] == 1
        assert point.fields["count_cumulative"] == 1
        assert point.fields["sum"] == pytest.approx(2.0)
        assert point.fields["sum_cumulative"] == pytest.approx(2.0)
        assert point.fields["avg"] == pytest.approx(2.0)
        assert point.fields["p50"] == pytest.approx(1.5)

    def test_histogram_update(self):
        test_message = {
            "name": "foo",
            "labels": ("bar", "baz"),
            "bin_counts": {("one", "two"): (0, 1, 1)},
            "sums": {("one", "two"): 2},
            "total_counts": {("one", "two"): 1},
            "bins": (1, 2, 3),
        }
        h = InfluxHistogram("foo", test_message)
        h.to_points(time_ns=1)  # establish baseline for delta calculation
        h.update(test_message)
        points = h.to_points(time_ns=2)
        point = points[0]
        assert point.fields["count"] == 1
        assert point.fields["count_cumulative"] == 2
        assert point.fields["sum"] == pytest.approx(2.0)
        assert point.fields["sum_cumulative"] == pytest.approx(4.0)
        assert point.fields["avg"] == pytest.approx(2.0)
        assert point.fields["p50"] == pytest.approx(1.5)
