import copy
import importlib.metadata
import logging
import time
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from numbers import Number
from typing import Any, Callable, DefaultDict, Sequence, Tuple


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
        # Local n, not self.bins: a factory closing over self would keep
        # pointing at the original Histogram after copy.deepcopy
        n = len(self.bins)
        self.bin_counts = defaultdict(lambda: [0] * n)
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
        yield (
            tuple(msg.get(i, "") for i in labels),
            1 if value_key is None else msg[value_key],
        )

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
        extractor=extractor(
            "test journey transaction location ex_type message".split()
        ),
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


# Processors that are only loaded when named in the include list, because they
# add series that most tests don't need
DEFAULT_EXCLUDED_PROCESSORS = frozenset({"mite_http_extended"})


def load_stats_entry_points(include=None, exclude=None, *, copy_stats=False):
    """Load every registered mite_stats entry point, applying include/exclude
    name filters. Shared by mite.stats.Stats and
    mite.cli.influxdb.influxdb_init so the two don't drift in how they
    handle a failing source.

    Processors in DEFAULT_EXCLUDED_PROCESSORS are skipped unless named in
    include.

    Module-level STATS lists are shared by every Stats() instance unless
    copied, which double-counts and clobbers dumps when several processors
    run concurrently (e.g. --influxdb=2). Stats passes copy_stats=True; a
    plugin whose stats can't be deep-copied is skipped entirely."""
    all_stats = []
    for entry_point in importlib.metadata.entry_points(group="mite_stats"):
        name = entry_point.name
        if include is not None and name not in include:
            continue
        if include is None and name in DEFAULT_EXCLUDED_PROCESSORS:
            continue
        if exclude is not None and name in exclude:
            continue
        logger.info(f"Registering stats processors from {name}")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                loaded_stats = entry_point.load()
        except ImportError as e:
            logger.warning(
                f"Not aggregating metrics from {name}: its stats processor "
                f"could not be loaded on this host: {e}"
            )
            continue
        except Exception as e:
            logger.error(f"Failed to load stats from entry point {name}: {e}")
            continue
        if copy_stats:
            try:
                loaded_stats = copy.deepcopy(loaded_stats)
            except Exception as e:
                logger.error(
                    f"Not aggregating metrics from {name}: its stats could "
                    f"not be copied: {e}"
                )
                continue
        all_stats += loaded_stats
    return all_stats


class Stats:
    def __init__(self, sender, include=None, exclude=None):
        self._all_stats = load_stats_entry_points(
            include=include, exclude=exclude, copy_stats=True
        )
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
