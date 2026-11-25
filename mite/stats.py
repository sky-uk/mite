import importlib.metadata
import logging
import time
import warnings
from collections import defaultdict
from dataclasses import dataclass
from numbers import Number
from typing import Any, Callable, ClassVar, Optional, Sequence, Tuple, Type


logger = logging.getLogger(__name__)


@dataclass
class Extractor:
    labels: Sequence[str]
    extract: Callable[[Any], Sequence[Tuple[str, Number]]]


class StatAggregation:
    """The running values one :class:`Aggregator` keeps for one :class:`Stat`.

    Each aggregator creates its own instance per stat, by calling
    ``stat.aggregation_class(stat)``, so aggregators never share data.

    To add a new kind of stat, subclass this and point a :class:`Stat`
    subclass's ``aggregation_class`` at it. Implement:

    * ``process(msg)``: called with every message; update the running values
      if ``self.stat.matcher(msg)`` matches.
    * ``dump()``: return the values gathered since the last dump, then reset
      them. The result must be in one of the three dump formats exporters
      understand (see :class:`CounterAggregation`, :class:`GaugeAggregation`
      and :class:`HistogramAggregation`), with ``"type"`` set to
      ``"Counter"``, ``"Gauge"`` or ``"Histogram"``.
    """

    def __init__(self, stat):
        self.stat = stat

    def process(self, msg):
        raise NotImplementedError

    def dump(self):
        raise NotImplementedError


class CounterAggregation(StatAggregation):
    """Counts matching messages per label combination."""

    def __init__(self, stat):
        super().__init__(stat)
        self.metrics = defaultdict(int)

    def process(self, msg):
        if self.stat.matcher(msg):
            for key, _ in self.stat.extractor.extract(msg):
                self.metrics[key] += 1

    def dump(self):
        metrics = dict(self.metrics)
        self.metrics.clear()
        return {
            "type": "Counter",
            "name": self.stat.name,
            "metrics": metrics,
            "labels": self.stat.extractor.labels,
        }


class AccumulatorAggregation(CounterAggregation):
    """Sums the extracted values per label combination; dumps as a Counter."""

    def process(self, msg):
        if self.stat.matcher(msg):
            for key, value in self.stat.extractor.extract(msg):
                self.metrics[key] += value


class GaugeAggregation(StatAggregation):
    """Keeps the latest extracted value per label combination."""

    def __init__(self, stat):
        super().__init__(stat)
        self.metrics = defaultdict(float)

    def process(self, msg):
        if self.stat.matcher(msg):
            for key, value in self.stat.extractor.extract(msg):
                self.metrics[key] = value

    def dump(self):
        metrics = dict(self.metrics)
        self.metrics.clear()
        return {
            "type": "Gauge",
            "name": self.stat.name,
            "metrics": metrics,
            "labels": self.stat.extractor.labels,
        }


class HistogramAggregation(StatAggregation):
    """Per label combination, keeps the sum and count of the extracted values
    and how many fall at or below each of the stat's bins."""

    def __init__(self, stat):
        super().__init__(stat)
        n = len(stat.bins)
        self.bin_counts = defaultdict(lambda: [0] * n)
        self.total_counts = defaultdict(int)
        self.sums = defaultdict(int)

    def process(self, msg):
        if self.stat.matcher(msg):
            for key, value in self.stat.extractor.extract(msg):
                self.sums[key] += value
                self.total_counts[key] += 1
                for i, bin in enumerate(self.stat.bins):
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
            "name": self.stat.name,
            "bin_counts": bin_counts,
            "sums": sums,
            "total_counts": total_counts,
            "bins": list(self.stat.bins),
            "labels": self.stat.extractor.labels,
        }


@dataclass(frozen=True)
class Stat:
    """Definition of a stat: what to measure, not the measurements.

    Plugins export lists of these through the ``mite_stats`` entry point.
    Definitions are immutable and shared by every :class:`Aggregator`; the
    running values live in the :class:`StatAggregation` each aggregator
    creates from ``aggregation_class``.

    Use one of :class:`Counter`, :class:`Accumulator`, :class:`Gauge` or
    :class:`Histogram`, or subclass this and set ``aggregation_class`` to add
    a new kind of stat.
    """

    aggregation_class: ClassVar[Optional[Type[StatAggregation]]] = None

    name: str
    matcher: Callable[[Any], bool]
    extractor: Extractor


@dataclass(frozen=True)
class Counter(Stat):
    """Counts matching messages."""

    aggregation_class = CounterAggregation


@dataclass(frozen=True)
class Accumulator(Stat):
    """Sums the values extracted from matching messages."""

    aggregation_class = AccumulatorAggregation


@dataclass(frozen=True)
class Gauge(Stat):
    """Reports the latest value extracted from matching messages."""

    aggregation_class = GaugeAggregation


@dataclass(frozen=True)
class Histogram(Stat):
    """Distribution of the values extracted from matching messages, bucketed
    by ``bins`` (stored sorted, as a tuple)."""

    aggregation_class = HistogramAggregation

    bins: Sequence[float]

    def __post_init__(self):
        object.__setattr__(self, "bins", tuple(sorted(self.bins)))


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


def load_stats_entry_points(include=None, exclude=None):
    """Load the Stat definitions from every registered mite_stats entry point,
    applying include/exclude name filters. Shared by mite.stats.Aggregator and
    mite.cli.influxdb.influxdb_init so the two don't drift in how they
    handle a failing source.

    Processors in DEFAULT_EXCLUDED_PROCESSORS are skipped unless named in
    include."""
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
                stats = list(entry_point.load())
            invalid = [
                s
                for s in stats
                if not isinstance(s, Stat) or s.aggregation_class is None
            ]
            if invalid:
                raise TypeError(
                    "expected mite.stats.Stat definitions with an "
                    f"aggregation_class, got {invalid!r}"
                )
            all_stats += stats
        except ImportError as e:
            logger.warning(
                f"Not aggregating metrics from {name}: its stats processor "
                f"could not be loaded on this host: {e}"
            )
        except Exception as e:
            logger.error(f"Failed to load stats from entry point {name}: {e}")
    return all_stats


class Aggregator:
    """Turns the raw message stream into periodic stat summaries.

    Runners emit one message per transaction, request, error and so on, which
    is far too many to export individually. The aggregator passes every
    message to each loaded stat, which updates its running values (counts,
    sums, latest values, histogram bins) per label combination. Every 0.25s
    it calls ``sender`` with a dump: a list with one summary per stat,
    covering the messages since the previous dump, and resets the values.

    Exporters (Prometheus, InfluxDB) consume these dumps, either over a
    socket from ``mite stats`` or in-process during ``mite ... test``.

    Each aggregator has its own :class:`StatAggregation` per stat, so several
    aggregators in one process never share or clear each other's data.

    Args:
        sender: Called with each dump.
        include: Names of the ``mite_stats`` entry points to load. Loads all
            except DEFAULT_EXCLUDED_PROCESSORS when omitted.
        exclude: Names of the ``mite_stats`` entry points to skip.
    """

    def __init__(self, sender, include=None, exclude=None):
        self._aggregations = [
            stat.aggregation_class(stat)
            for stat in load_stats_entry_points(include=include, exclude=exclude)
        ]
        self.sender = sender
        self.dump_timeout = time.time() + 0.25

    def process(self, msg):
        for aggregation in self._aggregations:
            aggregation.process(msg)
        t = time.time()
        if t > self.dump_timeout:
            self.sender(self.dump())
            self.dump_timeout = t + 0.25

    def dump(self):
        return [aggregation.dump() for aggregation in self._aggregations]


Stats = Aggregator
