from textwrap import dedent

from mite.stats_outputs.prometheus import PrometheusMetrics


def _counter(value, labels=("one", "two")):
    return {"type": "Counter", "name": "foo", "labels": ("bar", "baz"), "metrics": {labels: value}}


def _gauge(value):
    return {**_counter(value), "type": "Gauge"}


def _histogram(**overrides):
    return {
        "type": "Histogram",
        "name": "foo",
        "labels": ("bar", "baz"),
        "bin_counts": {("one", "two"): (0, 1, 1)},
        "sums": {("one", "two"): 2},
        "total_counts": {("one", "two"): 1},
        "bins": (1, 2, 3),
        **overrides,
    }


def _format(*dumps):
    metrics = PrometheusMetrics()
    for dump in dumps:
        metrics.send(dump)
    return metrics.format()


class TestCounter:
    def test_counter_serialize(self):
        assert _format([_counter(1)]) == dedent(
            """\
        # TYPE foo counter
        foo {bar="one",baz="two"} 1"""
        )

    def test_counter_update(self):
        assert _format([_counter(1)], [_counter(1)]) == dedent(
            """\
        # TYPE foo counter
        foo {bar="one",baz="two"} 2"""
        )

    def test_counter_first_seen_in_a_later_dump_is_an_integer(self):
        assert _format([_counter(1)], [_counter(1, labels=("three", "four"))]) == dedent(
            """\
        # TYPE foo counter
        foo {bar="one",baz="two"} 1
        foo {bar="three",baz="four"} 1"""
        )


class TestGauge:
    def test_gauge_serialize(self):
        assert _format([_gauge(1)]) == dedent(
            """\
        # TYPE foo gauge
        foo {bar="one",baz="two"} 1"""
        )

    def test_gauge_update(self):
        assert _format([_gauge(1)], [_gauge(5)]) == dedent(
            """\
        # TYPE foo gauge
        foo {bar="one",baz="two"} 5"""
        )


class TestHistogram:
    def test_histogram_serialize(self):
        assert _format([_histogram()]) == dedent(
            """\
        # TYPE foo histogram
        foo_bucket{bar="one",baz="two",le="1.000000"} 0
        foo_bucket{bar="one",baz="two",le="2.000000"} 1
        foo_bucket{bar="one",baz="two",le="3.000000"} 1
        foo_bucket{bar="one",baz="two",le="+Inf"} 1
        foo_sum{bar="one",baz="two"} 2.000000
        foo_count{bar="one",baz="two"} 1"""
        )

    def test_histogram_update(self):
        assert _format([_histogram()], [_histogram()]) == dedent(
            """\
        # TYPE foo histogram
        foo_bucket{bar="one",baz="two",le="1.000000"} 0
        foo_bucket{bar="one",baz="two",le="2.000000"} 2
        foo_bucket{bar="one",baz="two",le="3.000000"} 2
        foo_bucket{bar="one",baz="two",le="+Inf"} 2
        foo_sum{bar="one",baz="two"} 4.000000
        foo_count{bar="one",baz="two"} 2"""
        )

    def test_histogram_format_with_empty_bin_count(self):
        dump = [_histogram(bin_counts={}, sums={("one", "two"): 5})]
        assert _format(dump) == dedent(
            """\
        # TYPE foo histogram
        foo_bucket{bar="one",baz="two",le="1.000000"} 0
        foo_bucket{bar="one",baz="two",le="2.000000"} 0
        foo_bucket{bar="one",baz="two",le="3.000000"} 0
        foo_bucket{bar="one",baz="two",le="+Inf"} 1
        foo_sum{bar="one",baz="two"} 5.000000
        foo_count{bar="one",baz="two"} 1"""
        )


def test_each_prometheus_output_has_its_own_totals():
    from unittest import mock

    from mite.stats_outputs import OutputURL
    from mite.stats_outputs.prometheus import prometheus_output

    with mock.patch("mite.stats_outputs.prometheus.threading.Thread"):
        first = prometheus_output(OutputURL.parse("prometheus://:9301"), {})
        second = prometheus_output(OutputURL.parse("prometheus://:9302"), {})
    first.send([_counter(1)])
    assert "foo" in first.format()
    assert second.format() == ""
