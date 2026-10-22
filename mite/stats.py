import importlib.metadata
import logging
import time
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from functools import partial
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


# Loaded directly rather than via [project.entry-points.mite_stats] - an
# entry point always imports the integration package's __init__.py first
# (Python initialises the parent package before any submodule), and that
# package now raises ModuleNotFoundError at import time when its optional
# dependency is absent (see mite_http/__init__.py and siblings). Resolving
# these from an explicit dict means mite's own six processors don't depend
# on packaging metadata being in sync with the source tree - a stale
# editable install's entry_points.txt can't cause a double registration
# (see _iter_stats_sources below) - and the pip-installed distribution's
# dist.name no longer needs to be checked to tell first-party from
# third-party (compare the old _is_first_party_entry_point, which this
# replaces).
_FIRST_PARTY_STATS = {
    "mite": "mite.stats:_MITE_STATS",
    "mite_finagle": "mite_finagle.stats:STATS",
    "mite_http": "mite_http.stats:STATS",
    "mite_kafka": "mite_kafka.stats:_KAFKA_STATS",
    "mite_playwright": "mite_playwright.stats:STATS",
    "mite_selenium": "mite_selenium.stats:STATS",
}

# Entry points whose dependency is deliberately not part of the default
# install (see pyproject.toml), so a load failure there is expected, not
# worth warning about. The other five join this set once 3.0.0 moves their
# dependencies into extras too.
_ABSENCE_EXPECTED = frozenset({"mite_playwright"})


def _load_spec(spec):
    """Resolve a "module:attr" spec, the same contract importlib.metadata's
    EntryPoint.load() uses - so _FIRST_PARTY_STATS can be loaded the same
    way as a third-party entry point, below."""
    module_name, attr = spec.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def _iter_stats_sources():
    """Yields (name, loader, is_first_party) for every stats source: mite's
    own six first, then every registered mite_stats entry point. An entry
    point whose name collides with one of mite's own is skipped - see
    _FIRST_PARTY_STATS's docstring for why a stale editable install could
    otherwise double-register every first-party stat."""
    for name, spec in _FIRST_PARTY_STATS.items():
        yield name, partial(_load_spec, spec), True
    for entry_point in importlib.metadata.entry_points(group="mite_stats"):
        if entry_point.name in _FIRST_PARTY_STATS:
            logger.warning(
                f"Ignoring entry point {entry_point.name!r}: this name is "
                "reserved for mite's own stats processors."
            )
            continue
        yield entry_point.name, entry_point.load, False


def load_stats_entry_points(include=None, exclude=None):
    """Load every stats source (mite's own six, plus every registered
    mite_stats entry point), applying include/exclude name filters. Shared
    by mite.stats.Stats and mite.cli.influxdb.influxdb_init so the two
    don't drift in how they handle a failing source."""
    all_stats = []
    for name, load, is_first_party in _iter_stats_sources():
        if include is not None and name not in include:
            continue
        if exclude is not None and name in exclude:
            continue
        logger.info(f"Registering stats processors from {name}")
        try:
            # Loading a processor imports its package, which may emit this
            # PR's own mite-3.0 deprecation FutureWarnings (see
            # mite_http/__init__.py and siblings) - correctly attributed to
            # a real journey's import site when a journey module does the
            # importing, but attributed to importlib internals here, since
            # this process is the one doing the importing, not a journey
            # author who could act on it. Suppressed for that reason; not
            # thread-safe (catch_warnings is process-global), which is fine
            # for a one-shot call at process startup.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", FutureWarning)
                all_stats += load()
        except ImportError as e:
            # Each mite_* integration package raises ModuleNotFoundError
            # (an ImportError subclass) at its own import time when its
            # optional third-party dependency isn't installed - loading its
            # stats processor imports that package's __init__.py, which
            # triggers the same raise. Metrics of this type simply won't be
            # aggregated on this host; the integration itself still works
            # wherever its dependency is installed (e.g. on the runners
            # sending these metrics). DEBUG for a dependency that isn't
            # even part of the default install (see _ABSENCE_EXPECTED) -
            # WARNING otherwise, since that host is missing something the
            # runners sending it metrics may well have.
            level = logging.DEBUG if name in _ABSENCE_EXPECTED else logging.WARNING
            logger.log(
                level,
                f"Not aggregating metrics from {name}: its stats processor "
                f"could not be loaded on this host: {e}",
            )
        except Exception as e:
            if is_first_party:
                # A bug in one of mite's own stats modules, not a missing
                # optional dependency - must not be silently swallowed.
                raise
            # A third-party plugin's own bug. docs/stats.rst documents
            # mite_stats as a public extension point for other teams'
            # code; a broken third-party plugin shouldn't take down every
            # other processor, including mite's own.
            logger.error(f"Failed to load stats from entry point {name}: {e}")
    return all_stats


class Stats:
    def __init__(self, sender, include=None, exclude=None):
        self._all_stats = load_stats_entry_points(include=include, exclude=exclude)
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
