from mite.stats import Counter, Gauge, Histogram, LabelExtractor, label_extractor

TXN_MSG = {
    'start_time': 1572604344.7903123,
    'end_time': 1572604346.0693598,
    'had_error': True,
    'type': 'txn',
    'time': 1572604346.0693617,
    'test': 'mite_project.file:scenario',
    'runner_id': 1,
    'journey': 'mite_project.file:journey',
    'context_id': 8,
    'scenario_id': 31,
    'scenario_data_id': 2,
    'transaction': 'txn_name',
    'transaction_id': 3,
}


def test_label_extractor_txn_msg():
    extractor = label_extractor("test journey transaction had_error".split())
    labels = extractor.extract(TXN_MSG)
    expected_value = (
        "mite_project.file:scenario",
        "mite_project.file:journey",
        "txn_name",
        True,
    )
    assert labels == expected_value


class TestCounter:
    dummy_lx = LabelExtractor(labels=("bar",), extract=lambda x: "foo")

    def test_process(self):
        counter = Counter("test", lambda x: True, self.dummy_lx)
        counter.process(None)
        assert dict(counter.metrics) == {"foo": 1}

    def test_process_additivity(self):
        counter = Counter("test", lambda x: True, self.dummy_lx)
        counter.process(None)
        counter.process(None)
        assert dict(counter.metrics) == {"foo": 2}

    def test_dump(self):
        counter = Counter("test", lambda x: True, self.dummy_lx)
        counter.process(None)
        assert counter.dump() == {
            "type": "Counter",
            "name": "test",
            "metrics": {"foo": 1},
            "labels": ("bar",),
        }
        assert dict(counter.metrics) == {}

    def test_process_after_dump(self):
        counter = Counter("test", lambda x: True, self.dummy_lx)
        counter.process(None)
        counter.dump()
        counter.process(None)
        assert dict(counter.metrics) == {"foo": 1}


class TestGauge:
    dummy_lx = LabelExtractor(labels=("bar",), extract=lambda x: "foo")

    def test_process(self):
        gauge = Gauge("test", lambda x: True, self.dummy_lx, lambda x: 3.0)
        gauge.process(None)
        assert dict(gauge.metrics) == {"foo": 3.0}

    def test_process_additivity(self):
        gauge = Gauge("test", lambda x: True, self.dummy_lx, lambda x: 3.0)
        gauge.process(None)
        gauge.process(None)
        assert dict(gauge.metrics) == {"foo": 6.0}

    def test_dump(self):
        gauge = Gauge("test", lambda x: True, self.dummy_lx, lambda x: 3.0)
        gauge.process(None)
        assert gauge.dump() == {
            "type": "Gauge",
            "name": "test",
            "metrics": {"foo": 3.0},
            "labels": ("bar",),
        }
        assert dict(gauge.metrics) == {}

    def test_process_after_dump(self):
        gauge = Gauge("test", lambda x: True, self.dummy_lx, lambda x: 3.0)
        gauge.process(None)
        gauge.dump()
        gauge.process(None)
        assert dict(gauge.metrics) == {"foo": 3.0}


class TestHistogram:
    dummy_lx = LabelExtractor(labels=("bar",), extract=lambda x: "foo")

    def test_process(self):
        hist = Histogram("test", lambda _: True, self.dummy_lx, lambda x: 3, (1, 2, 3, 4))
        hist.process(None)
        assert dict(hist.bin_counts) == {"foo": [1, 1, 1, 0]}
        assert dict(hist.sums) == {"foo": 3}
        assert dict(hist.total_counts) == {"foo": 1}

    def test_process_additivity(self):
        hist = Histogram("test", lambda _: True, self.dummy_lx, lambda x: 3, (1, 2, 3, 4))
        hist.process(None)
        hist.process(None)
        assert dict(hist.bin_counts) == {"foo": [2, 2, 2, 0]}
        assert dict(hist.sums) == {"foo": 6}
        assert dict(hist.total_counts) == {"foo": 2}

    def test_dump(self):
        hist = Histogram("test", lambda _: True, self.dummy_lx, lambda x: 3, (1, 2, 3, 4))
        hist.process(None)
        assert hist.dump() == {
            "type": "Histogram",
            "name": "test",
            "bin_counts": {"foo": [1, 1, 1, 0]},
            "sums": {"foo": 3},
            "total_counts": {"foo": 1},
            "bins": [1, 2, 3, 4],
            "labels": ("bar",),
        }
        assert dict(hist.total_counts) == {}
        assert dict(hist.sums) == {}
        assert dict(hist.bin_counts) == {}

    def test_process_after_dump(self):
        hist = Histogram("test", lambda _: True, self.dummy_lx, lambda x: 3, (1, 2, 3, 4))
        hist.process(None)
        hist.dump()
        hist.process(None)
        assert dict(hist.bin_counts) == {"foo": [1, 1, 1, 0]}
        assert dict(hist.sums) == {"foo": 3}
        assert dict(hist.total_counts) == {"foo": 1}
