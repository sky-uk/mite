import logging
import math
import statistics
import time
from collections import defaultdict

from .utils import spec_import


class MsgOutput:
    def __init__(self, opts):
        self._logger = logging.getLogger("MSG")

    def process_message(self, msg):
        stacktrace = msg.pop("stacktrace", None)
        if stacktrace and self._logger.isEnabledFor(logging.WARNING):
            message = msg.pop("message", None)
            ex_type = msg.pop("ex_type", None)
            start = f'[{msg.pop("type", None)}] {msg.pop("time", None):.6f}'
            end = ", ".join(f"{k}={v}" for k, v in sorted(msg.items()))
            self._logger.warning(
                "%s %s\n%s: %s\n%s", start, end, ex_type, message, stacktrace
            )
        elif self._logger.isEnabledFor(logging.DEBUG):
            start = f'[{msg.pop("type", None)}] {msg.pop("time", None):.6f}'
            end = ", ".join(f"{k}={v}" for k, v in sorted(msg.items()))
            self._logger.debug("%s %s", start, end)


class DebugMessageOutput:
    def __init__(self, opts):
        self._logger = logging.getLogger("Debug Logger")

    def process_message(self, message):
        text = message.get("text")
        if message.get("type") == "debug_console_message" and text:
            self._logger.info(text)


# Keep in sync with the --benchmark-percentiles default in mite/__main__.py
DEFAULT_BENCHMARK_PERCENTILES = "50:0,90:0,98:0,99:0"
# Config key for percentiles applying to every transaction without its own entry
ALL_TRANSACTIONS_KEY = "*"


def _validated(pct_thresholds, source):
    for percentile, threshold in pct_thresholds:
        if not 1 <= percentile <= 99:
            raise ValueError(f"{source}: percentile {percentile} must be between 1 and 99")
        if threshold < 0:
            raise ValueError(f"{source}: threshold {threshold} must not be negative")
    return pct_thresholds


def _parse_pct_spec(spec):
    """Parse a "percentile:threshold_ms,..." string into [(int, int), ...]."""
    if not spec:
        return []
    return _validated(
        [
            (int(percentile), int(threshold))
            for percentile, threshold in (p.split(":") for p in spec.split(","))
        ],
        spec,
    )


def _pct_dict_to_list(pcts, source):
    if not isinstance(pcts, dict):
        raise ValueError(
            f"{source}: expected a {{percentile: threshold_ms}} dict, got {pcts!r}"
        )
    return _validated(
        [(int(percentile), int(threshold)) for percentile, threshold in pcts.items()],
        source,
    )


def load_benchmark_percentiles(value):
    """Resolve --benchmark-percentiles into (global_spec, {transaction: spec}).

    `value` is either the inline "percentile:threshold_ms,..." format, or a mite
    spec ("module:attribute") naming a flat dict keyed by transaction name,
    matched exactly (nested transactions use their full "outer :: inner" name):

        {
            "*": {50: 0, 90: 200},
            "Login": {90: 300, 99: 800},
            "Login :: Fetch token": {99: 500},
        }

    "*" sets the percentiles for the whole run only, exactly as the inline
    format does; it is a literal key, not a wildcard pattern. Only transactions
    with their own entry are tracked, reported and checked against thresholds.

    Module names can't start with a digit, which distinguishes the two forms.
    """
    # TODO: discuss whether we're happy with this flat "*" + transaction name
    # keyed dict as the DSL for benchmark thresholds.
    value = value or DEFAULT_BENCHMARK_PERCENTILES
    if value[0].isdigit():
        return _parse_pct_spec(value), {}

    config = spec_import(value)
    if not isinstance(config, dict):
        raise ValueError(
            f"--benchmark-percentiles spec {value} must refer to a dict, "
            f"got {type(config).__name__}"
        )
    global_spec = (
        _pct_dict_to_list(
            config[ALL_TRANSACTIONS_KEY], f"{value}[{ALL_TRANSACTIONS_KEY!r}]"
        )
        if ALL_TRANSACTIONS_KEY in config
        else _parse_pct_spec(DEFAULT_BENCHMARK_PERCENTILES)
    )
    transaction_specs = {
        transaction: _pct_dict_to_list(pcts, f"{value}[{transaction!r}]")
        for transaction, pcts in config.items()
        if transaction != ALL_TRANSACTIONS_KEY
    }
    return global_spec, transaction_specs


class _StatsBucket:
    """Response time and throughput samples for a run, or one transaction of a run."""

    def __init__(self):
        self.resp_times = []
        self.recent_resp_times = []
        self.req_sec_store = []
        self.req_total = 0
        self.req_recent = 0
        self.error_total = 0
        self.error_recent = 0
        self.data_transferred = 0

    def add_response(self, total_time, download_size=0):
        self.recent_resp_times.append(total_time)
        self.data_transferred += download_size
        self.req_total += 1
        self.req_recent += 1

    def add_error(self):
        self.error_total += 1
        self.error_recent += 1

    def flush(self, elapsed=None):
        """Move the current period into the run totals.

        Pass `elapsed` to record a req/s sample for the period; omit it for a
        partial period, whose rate would not be comparable to full periods.
        """
        self.resp_times.extend(self.recent_resp_times)
        if elapsed and self.req_recent:
            self.req_sec_store.append(self.req_recent / elapsed)
        self.recent_resp_times.clear()
        self.req_recent = 0
        self.error_recent = 0

    def percentiles(self, pct_thresholds):
        """Return [(percentile, threshold, value_or_None), ...]."""
        if len(self.resp_times) < 2:
            return [(p, t, None) for p, t in pct_thresholds]
        quantiles = statistics.quantiles(self.resp_times, n=100)
        return [(p, t, quantiles[p - 1]) for p, t in pct_thresholds]

    @property
    def resp_time_mean(self):
        return _mean(self.resp_times)

    @property
    def resp_time_min(self):
        return min(self.resp_times, default=None)

    @property
    def resp_time_max(self):
        return max(self.resp_times, default=None)

    @property
    def resp_time_stdev(self):
        return _stdev(self.resp_times)

    @property
    def resp_time_within_stdev(self):
        return _within_stdev(self.resp_times)

    @property
    def req_sec_mean(self):
        return _mean(self.req_sec_store)

    @property
    def req_sec_min(self):
        return min(self.req_sec_store, default=None)

    @property
    def req_sec_max(self):
        return max(self.req_sec_store, default=None)

    @property
    def req_sec_stdev(self):
        return _stdev(self.req_sec_store)

    @property
    def req_sec_within_stdev(self):
        return _within_stdev(self.req_sec_store)


def _mean(samples):
    return statistics.fmean(samples) if samples else None


def _stdev(samples):
    return statistics.stdev(samples) if len(samples) >= 2 else None


def _within_stdev(samples):
    """Percentage of samples within mean +/- one standard deviation."""
    stdev = _stdev(samples)
    if stdev is None:
        return None
    mean = statistics.fmean(samples)
    return sum(abs(x - mean) < stdev for x in samples) / len(samples) * 100


class GenericStatsOutput:
    def __init__(self, opts, period=2):
        self._period = period
        # get the state of the journey_logging attribute from the
        # opts dictionary
        self._journey_logging = opts.get("--journey-logging", False)
        if self._journey_logging is not False:
            self._journey_logging = True
        self._hide_constant_logs = opts.get("--hide-constant-logs")
        self._report = opts.get("--report")
        self._logger = logging.getLogger(f"{self.log_name} Stats")
        self._init_time = time.time()
        self._start_t = None
        self._scenarios_completed_time = 0
        self._global = _StatsBucket()
        self._error_journeys = defaultdict(int)
        # TODO: decide whether a transaction's percentiles should stand alone
        # (current behaviour) or be merged over the "*" percentiles.
        self._pct_spec, self._transaction_pct_specs = load_benchmark_percentiles(
            opts.get("--benchmark-percentiles")
        )
        # Only configured transactions are tracked, keyed by their full (nested)
        # name; they're reported even with no samples. Everything else only
        # counts towards the global stats.
        # TODO: consider also rolling nested transactions up into their parents.
        self._transactions = {
            transaction: _StatsBucket() for transaction in self._transaction_pct_specs
        }

    def _pct(self, percentile):
        """Percentile calculation with linear interpolation.

        If the samples have an exact split at `percentile`, return that single
        value; otherwise interpolate the nearest two values.

        Requires that the recent response times are sorted.

        """
        samples = self._global.recent_resp_times
        if not samples:
            return "None"
        assert 0 <= percentile <= 100
        index = (percentile / 100) * (len(samples) - 1)
        fractional_index, index = math.modf(index)
        index = int(index)
        if fractional_index == 0:
            return f"{samples[index]:.6f}"
        a = samples[index]
        b = samples[index + 1]
        interpolated_amount = (b - a) * fractional_index
        return f"{a + interpolated_amount:.6f}"

    @property
    def error_total(self):
        return self._global.error_total

    def print_output(self, t):
        dt = t - self._start_t
        recent = self._global
        recent.recent_resp_times.sort()
        if not self._hide_constant_logs:
            self._logger.info(
                f"Total> #Reqs:{recent.req_total} #Errs:{recent.error_total}"
            )
        # only output journey logs if the --journey_logging switch is set
        if self._journey_logging:
            for journey, errors in self._error_journeys.items():
                self._logger.info(f"Total errors for {journey} :{errors}")
        if not self._hide_constant_logs:
            self._logger.info(
                f"Last {self._period} Secs> #Reqs:{recent.req_recent} #Errs:{recent.error_recent} "
                + f"Req/S:{recent.req_recent / dt:.1f} min:{self._pct(0)} "
                + f"25%:{self._pct(25)} 50%:{self._pct(50)} 75%:{self._pct(75)} "
                + f"90%:{self._pct(90)} 99%:{self._pct(99)} 99.9%:{self._pct(99.9)} "
                + f"max:{self._pct(100)}",
            )

    def _buckets(self):
        yield self._global
        yield from self._transactions.values()

    def _end_period(self, t):
        self.print_output(t)
        elapsed = t - self._start_t
        for bucket in self._buckets():
            bucket.flush(elapsed)
        self._start_t = t

    def finalise(self):
        """Fold the final, partial period into the run totals.

        Its response times are kept, but no req/s sample is recorded as the
        rate over a truncated period isn't comparable to full periods.
        """
        for bucket in self._buckets():
            bucket.flush()

    def _buckets_for(self, message):
        yield self._global
        bucket = self._transactions.get(message.get("transaction"))
        if bucket is not None:
            yield bucket

    def process_message(self, message):
        if "type" not in message:
            return
        msg_type = message["type"]
        t = time.time()
        if self._start_t is None:
            self._start_t = t
        if self._start_t + self._period < t:
            self._end_period(t)
        if msg_type in self.message_types:
            for bucket in self._buckets_for(message):
                bucket.add_response(message["total_time"], message.get("download_size", 0))
        elif msg_type in ("error", "exception"):
            for bucket in self._buckets_for(message):
                bucket.add_error()
            if self._journey_logging:
                self._error_journeys[message.get("journey")] += 1

    @property
    def transaction_stats(self):
        return dict(self._transactions)

    @property
    def percentiles_by_transaction(self):
        return {
            transaction: bucket.percentiles(self._transaction_pct_specs[transaction])
            for transaction, bucket in self._transactions.items()
        }

    @property
    def percentiles_list_resp_time_store(self):
        if not self._global.resp_times:
            return []
        return self._global.percentiles(self._pct_spec)

    # Run-level accessors, returning 0 rather than None for threshold checks
    @property
    def _req_total(self):
        return self._global.req_total

    @property
    def _data_transferred(self):
        return self._global.data_transferred

    @property
    def _resp_time_min(self):
        return self._global.resp_time_min or 0

    @property
    def _resp_time_max(self):
        return self._global.resp_time_max or 0

    @property
    def _req_sec_min(self):
        return self._global.req_sec_min or 0

    @property
    def _req_sec_max(self):
        return self._global.req_sec_max or 0

    @property
    def mean_resp_time(self):
        return self._global.resp_time_mean or 0

    @property
    def req_sec_mean(self):
        return self._global.req_sec_mean or 0

    @property
    def resp_time_standard_deviation(self):
        return self._global.resp_time_stdev or 0

    @property
    def req_sec_standard_deviation(self):
        return self._global.req_sec_stdev or 0

    @property
    def resp_time_within_standard_deviation(self):
        return self._global.resp_time_within_stdev or 0

    @property
    def req_sec_within_standard_deviation(self):
        return self._global.req_sec_within_stdev or 0


class HttpStatsOutput(GenericStatsOutput):
    message_types = {
        "http_metrics",
        "selenium_page_load_metrics",
        "selenium_network_resource_metrics",
    }
    log_name = "Http"


class FinagleStatsOutput(GenericStatsOutput):
    message_types = {"finagle_metrics"}
    log_name = "Finagle"
