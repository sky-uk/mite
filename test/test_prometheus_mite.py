from textwrap import dedent

from mite.web.prometheus import Counter, Gauge, Histogram


class TestCounter:
    def test_counter_serialize(self):
        test_message = {
            "name": "foo",
            "labels": ("bar", "baz"),
            "metrics": {("one", "two"): 1},
        }
        c = Counter("foo", test_message)
        f = c.format()
        assert f == dedent(
            """\
        # TYPE foo counter
        foo {bar="one",baz="two"} 1"""
        )

    def test_counter_update(self):
        test_message = {
            "name": "foo",
            "labels": ("bar", "baz"),
            "metrics": {("one", "two"): 1},
        }
        c = Counter("foo", test_message)
        c.update(test_message)
        f = c.format()
        assert f == dedent(
            """\
        # TYPE foo counter
        foo {bar="one",baz="two"} 2"""
        )


class TestGauge:
    def test_gauge_serialize(self):
        test_message = {
            "name": "foo",
            "labels": ("bar", "baz"),
            "metrics": {("one", "two"): 1},
        }
        c = Gauge("foo", test_message)
        f = c.format()
        assert f == dedent(
            """\
        # TYPE foo gauge
        foo {bar="one",baz="two"} 1"""
        )

    def test_gauge_update(self):
        test_message = {
            "name": "foo",
            "labels": ("bar", "baz"),
            "metrics": {("one", "two"): 1},
        }
        c = Gauge("foo", test_message)
        c.update(test_message)
        f = c.format()
        assert f == dedent(
            """\
        # TYPE foo gauge
        foo {bar="one",baz="two"} 1"""
        )


class TestHistogram:
    def test_histogram_serialize(self):
        test_message = {
            "name": "foo",
            "labels": ("bar", "baz"),
            "bin_counts": {("one", "two"): (0, 1, 1)},
            "sums": {("one", "two"): 2},
            "total_counts": {("one", "two"): 1},
            "bins": (1, 2, 3),
        }
        h = Histogram("foo", test_message)
        f = h.format()
        assert f == dedent(
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
        test_message = {
            "name": "foo",
            "labels": ("bar", "baz"),
            "bin_counts": {("one", "two"): (0, 1, 1)},
            "sums": {("one", "two"): 2},
            "total_counts": {("one", "two"): 1},
            "bins": (1, 2, 3),
        }
        h = Histogram("foo", test_message)
        h.update(test_message)
        f = h.format()
        assert f == dedent(
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
        test_message = {
            "name": "foo",
            "labels": ("bar", "baz"),
            "bin_counts": {},
            "sums": {("one", "two"): 5},
            "total_counts": {("one", "two"): 1},
            "bins": (1, 2, 3),
        }
        h = Histogram("foo", test_message)
        f = h.format()
        assert f == dedent(
            """\
        # TYPE foo histogram
        foo_bucket{bar="one",baz="two",le="1.000000"} 0
        foo_bucket{bar="one",baz="two",le="2.000000"} 0
        foo_bucket{bar="one",baz="two",le="3.000000"} 0
        foo_bucket{bar="one",baz="two",le="+Inf"} 1
        foo_sum{bar="one",baz="two"} 5.000000
        foo_count{bar="one",baz="two"} 1"""
        )
