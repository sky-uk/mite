import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from numbers import Number
from typing import Any, Callable, DefaultDict, Sequence, Tuple

import pkg_resources

logger = logging.getLogger(__name__)


@dataclass
class Extractor:
    labels: Sequence[str]
    extract: Callable[[Any], Sequence[Tuple[str, Number]]]


@dataclass
class Stat:
    name: str
    matcher: Callable[[Any], bool]
    extractor: Extractor


@dataclass
class _CounterBase(Stat):
    metrics: DefaultDict[Any, int] = field(
        default_factory=lambda: defaultdict(int), init=False
    )

    def process(self, msg):
        raise NotImplementedError

    def dump(self):
        metrics = dict(self.metrics)
        self.metrics.clear()
        return {
            "type": "Counter",
            "name": self.name,
            "metrics": metrics,
            "labels": self.extractor.labels,
        }


@dataclass
class Counter(_CounterBase):
    def process(self, msg):
        if self.matcher(msg):
            for key, _ in self.extractor.extract(msg):
                self.metrics[key] += 1


@dataclass
class Accumulator(_CounterBase):
    def process(self, msg):
        if self.matcher(msg):
            for key, value in self.extractor.extract(msg):
                self.metrics[key] += value


@dataclass
class Gauge(Stat):
    metrics: DefaultDict[Any, float] = field(
        default_factory=lambda: defaultdict(float), init=False
    )

    def process(self, msg):
        if self.matcher(msg):
            for key, value in self.extractor.extract(msg):
                self.metrics[key] = value

    def dump(self):
        metrics = dict(self.metrics)
        self.metrics.clear()
        return {
            "type": "Gauge",
            "name": self.name,
            "metrics": metrics,
            "labels": self.extractor.labels,
        }


@dataclass
class Histogram(Stat):
    bins: Sequence[float]

    def __post_init__(self):
        self.bins = sorted(self.bins)
        self.bin_counts = defaultdict(lambda: [0 for _ in range(len(self.bins))])
        self.total_counts = defaultdict(int)
        self.sums = defaultdict(int)

    def process(self, msg):
        if self.matcher(msg):
            for key, value in self.extractor.extract(msg):
                self.sums[key] += value
                self.total_counts[key] += 1
                for i, bin in enumerate(self.bins):
                    if value <= bin:
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
            "labels": self.extractor.labels,
        }


def matcher_by_type(*targets):
    def type_matcher(msg):
        logger.debug(f"message to match by type: {msg}")
        return msg.get("type", None) in targets

    return type_matcher


def extractor(labels, value_key=None):
    def extract_items(msg):
        yield tuple(msg.get(i, "") for i in labels), 1 if value_key is None else msg[
            value_key
        ]

    extract_items.labels = labels
    return Extractor(labels=labels, extract=extract_items)


def controller_report_extractor(dict_key):
    def extract_items(msg):
        for scenario_id, value in msg[dict_key].items():
            yield (msg.get("test", ""), scenario_id), value

    return Extractor(labels=("test", "scenario_id"), extract=extract_items)


_MITE_STATS = [
    Counter(
        name="mite_journey_error_total",
        matcher=matcher_by_type("error", "exception"),
        extractor=extractor("test journey transaction location ex_type message".split()),
    ),
    Counter(
        name="mite_transaction_total",
        matcher=matcher_by_type("txn"),
        extractor=extractor("test journey transaction had_error".split()),
    ),
    Gauge(
        name="mite_actual_count",
        matcher=matcher_by_type("controller_report"),
        extractor=controller_report_extractor("actual"),
    ),
    Gauge(
        name="mite_required_count",
        matcher=matcher_by_type("controller_report"),
        extractor=controller_report_extractor("required"),
    ),
    Gauge(
        name="mite_runner_count",
        matcher=matcher_by_type("controller_report"),
        extractor=extractor(["test"], "num_runners"),
    ),
]


class Stats:
    def __init__(self, sender, include=None, exclude=None):
        self._all_stats = []
        for entry_point in pkg_resources.iter_entry_points("mite_stats"):
            if include is not None and entry_point.name not in include:
                continue
            if exclude is not None and entry_point.name in exclude:
                continue
            logging.info(f"Registering stats processors from {entry_point.name}")
            self._all_stats += entry_point.load()

        self.sender = sender
        self.dump_timeout = time.time() + 0.25

    def process(self, msg):
        for processor in self._all_stats:
            processor.process(msg)
        t = time.time()
        if t > self.dump_timeout:
            self.sender(self.dump())
            self.dump_timeout = t + 0.25

    def dump(self):
        return [i.dump() for i in self._all_stats]
