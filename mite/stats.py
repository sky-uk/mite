import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, DefaultDict, Sequence

logger = logging.getLogger(__name__)


@dataclass
class LabelExtractor:
    labels: Sequence[str]
    extract: Callable[[Any], Sequence[str]]


@dataclass
class Stat:
    name: str
    matcher: Callable[[Any], bool]
    label_extractor: LabelExtractor


@dataclass
class Counter(Stat):
    metrics: DefaultDict[Any, int] = field(
        default_factory=lambda: defaultdict(int), init=False
    )

    def process(self, msg):
        if self.matcher(msg):
            key = self.label_extractor.extract(msg)
            self.metrics[key] += 1

    def dump(self):
        metrics = dict(self.metrics)
        self.metrics.clear()
        return {
            "type": "Counter",
            "name": self.name,
            "metrics": metrics,
            "labels": self.label_extractor.labels,
        }


@dataclass
class Gauge(Stat):
    value_extractor: Callable[[Any], float]
    metrics: DefaultDict[Any, float] = field(
        default_factory=lambda: defaultdict(float), init=False
    )

    def process(self, msg):
        if self.matcher(msg):
            key = self.label_extractor.extract(msg)
            self.metrics[key] += self.value_extractor(msg)

    def dump(self):
        metrics = dict(self.metrics)
        self.metrics.clear()
        return {
            "type": "Gauge",
            "name": self.name,
            "metrics": metrics,
            "labels": self.label_extractor.labels,
        }


@dataclass
class Histogram(Stat):
    value_extractor: Callable[[Any], float]
    bins: Sequence[float]

    def __post_init__(self):
        self.bins = sorted(self.bins)
        self.bin_counts = defaultdict(lambda: [0 for _ in range(len(self.bins))])
        self.total_counts = defaultdict(int)
        self.sums = defaultdict(int)

    def process(self, msg):
        if self.matcher(msg):
            key = self.label_extractor.extract(msg)
            value = self.value_extractor(msg)

            self.sums[key] += value
            self.total_counts[key] += 1
            for i, bin in enumerate(self.bins):
                if bin <= value:
                    self.bin_counts[key][i] += 1

    def dump(self):
        bin_counts = dict(self.bin_counts)
        sums = dict(self.sums)
        total_counts = dict(self.total_counts)
        self.bin_counts.clear()
        self.sums.clear()
        self.total_counts.clear()

        return {
            "type": "Histogram",
            "name": self.name,
            "bin_counts": bin_counts,
            "sums": sums,
            "total_counts": total_counts,
            "bins": self.bins,
            "labels": self.label_extractor.labels,
        }


def matcher_by_type(*targets):
    def type_matcher(msg):
        logger.debug("message to match by type: %s" % (msg,))
        return msg.get("type", None) in targets

    return type_matcher


def label_extractor(labels):
    return LabelExtractor(
        labels=labels, extract=lambda msg: tuple(msg.get(label, "") for label in labels)
    )


# FIXME WIP: remove these three
def labels_and_value_extractor(labels, value_key):
    def extract_items(msg):
        yield tuple(msg.get(i, '') for i in labels), msg[value_key]

    extract_items.labels = labels
    return extract_items


def time_extractor():
    def extract_items(msg):
        yield (), time.time() - msg['time']

    extract_items.labels = ''
    return extract_items


def controller_report_extractor(dict_key):
    def extract_items(msg):
        for scenario_id, value in msg[dict_key].items():
            yield (msg.get('test', ''), scenario_id), value

    extract_items.labels = ('test', 'scenario_id')
    return extract_items


class Stats:
    def __init__(self, sender):
        self.sender = sender
        self.processors = [
            Counter(
                name='mite_journey_error_total',
                matcher=matcher_by_type('error', 'exception'),
                label_extractor=label_extractor(
                    'test journey transaction location message'.split()
                ),
            ),
            Counter(
                name='mite_transaction_total',
                matcher=matcher_by_type('txn'),
                label_extractor=label_extractor(
                    'test journey transaction had_error'.split()
                ),
            ),
            Counter(
                name='mite_http_response_total',
                matcher=matcher_by_type('http_curl_metrics'),
                label_extractor=label_extractor(
                    'test journey transaction method response_code'.split()
                ),
            ),
            Histogram(
                name='mite_http_response_time_seconds',
                matcher=matcher_by_type('http_curl_metrics'),
                label_extractor=label_extractor(['transaction']),
                value_extractor=lambda x: x['total_time'],
                bins=[
                    0.0001,
                    0.001,
                    0.01,
                    0.05,
                    0.1,
                    0.2,
                    0.4,
                    0.8,
                    1,
                    2,
                    4,
                    8,
                    16,
                    32,
                    64,
                ],
            ),
            Gauge(
                name='mite_actual_count',
                matcher=matcher_by_type('controller_report'),
                label_extractor=controller_report_extractor('actual'),
            ),
            Gauge(
                'mite_required_count',
                matcher_by_type('controller_report'),
                controller_report_extractor('required'),
            ),
            Gauge(
                'mite_runner_count',
                matcher_by_type('controller_report'),
                labels_and_value_extractor(['test'], 'num_runners'),
            ),
            Histogram(
                'mite_http_selenium_response_time_seconds',
                matcher_by_type('http_selenium_metrics'),
                labels_and_value_extractor(['transaction'], 'total_time'),
                [0.0001, 0.001, 0.01, 0.05, 0.1, 0.2, 0.4, 0.8, 1, 2, 4, 8, 16, 32, 64],
            ),
            Counter(
                'mite_http_selenium_response_total',
                matcher_by_type('http_selenium_metrics'),
                label_extractor('test journey transaction'.split()),
            ),
        ]
        self.dump_timeout = time.time() + 0.25

    def process(self, msg):
        for processor in self.processors:
            processor.process(msg)
        t = time.time()
        if t > self.dump_timeout:
            self.sender(self.dump())
            self.dump_timeout = t + 0.25

    def dump(self):
        return [i.dump() for i in self.processors]
