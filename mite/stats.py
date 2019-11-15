import time
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class Counter:
    def __init__(self, name, matcher, labels_extractor):
        self._name = name
        self._matcher = matcher
        self._labels_extractor = labels_extractor
        self._metrics = defaultdict(int)

    def process(self, msg):
        if self._matcher(msg):
            for key in self._labels_extractor(msg):
                self._metrics[key] += 1

    def dump(self):
        metrics = dict(self._metrics)
        self._metrics.clear()
        return {
            'type': 'Counter',
            'name': self._name,
            'metrics': metrics,
            'labels': self._labels_extractor.labels,
        }


class Gauge:
    def __init__(self, name, matcher, labels_and_value_extractor):
        self._name = name
        self._matcher = matcher
        self._labels_and_value_extractor = labels_and_value_extractor
        self._metrics = defaultdict(float)

    def process(self, msg):
        if self._matcher(msg):
            for key, value in self._labels_and_value_extractor(msg):
                self._metrics[key] += value

    def dump(self):
        metrics = dict(self._metrics)
        self._metrics.clear()
        return {
            'type': 'Gauge',
            'name': self._name,
            'metrics': metrics,
            'labels': self._labels_and_value_extractor.labels,
        }


class Histogram:
    def __init__(self, name, matcher, labels_and_value_extractor, bins):
        self._name = name
        self._matcher = matcher
        self._labels_and_value_extractor = labels_and_value_extractor
        self._bin_counts = {}
        self._sums = {}
        self._total_counts = {}
        self._bins = bins

    def process(self, msg):
        if self._matcher(msg):
            for key, value in self._labels_and_value_extractor(msg):
                if key not in self._bin_counts:
                    bins = [0 for _ in self._bins]
                    self._bin_counts[key] = bins
                    self._sums[key] = value
                    self._total_counts[key] = 1
                else:
                    bins = self._bin_counts[key]
                    self._sums[key] += value
                    self._total_counts[key] += 1
                for i, bin_value in enumerate(self._bins):
                    if value <= bin_value:
                        bins[i] += 1

    def dump(self):
        bin_counts = dict(self._bin_counts)
        sums = dict(self._sums)
        total_counts = dict(self._total_counts)
        self._bin_counts.clear()
        self._sums.clear()
        self._total_counts.clear()
        return {
            'type': 'Histogram',
            'name': self._name,
            'bin_counts': bin_counts,
            'sums': sums,
            'total_counts': total_counts,
            'bins': self._bins,
            'labels': self._labels_and_value_extractor.labels,
        }


def matcher_by_type(*targets):
    def type_matcher(msg):
        logger.debug("message to match by type: %s" % (msg,))
        return 'type' in msg and msg['type'] in targets

    return type_matcher


def labels_extractor(labels):
    def extract_items(msg):
        yield tuple(msg.get(i, '') for i in labels)

    extract_items.labels = labels
    return extract_items


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
                'mite_journey_error_total',
                matcher_by_type('error', 'exception'),
                labels_extractor('test journey transaction location message'.split()),
            ),
            Counter(
                'mite_transaction_total',
                matcher_by_type('txn'),
                labels_extractor('test journey transaction had_error'.split()),
            ),
            Counter(
                'mite_http_response_total',
                matcher_by_type('http_curl_metrics'),
                labels_extractor('test journey transaction method response_code'.split()),
            ),
            Histogram(
                'mite_http_response_time_seconds',
                matcher_by_type('http_curl_metrics'),
                labels_and_value_extractor(['transaction'], 'total_time'),
                [0.0001, 0.001, 0.01, 0.05, 0.1, 0.2, 0.4, 0.8, 1, 2, 4, 8, 16, 32, 64],
            ),
            Gauge(
                'mite_actual_count',
                matcher_by_type('controller_report'),
                controller_report_extractor('actual'),
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
                labels_extractor('test journey transaction'.split()),
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
