import logging
import math
import statistics
import time
from collections import defaultdict


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


def _parse_pct_spec(spec):
    """Parse a "percentile:threshold_ms,..." string into [(int, int), ...]."""
    if not spec:
        return []
    return [
        (int(percentile), int(threshold))
        for percentile, threshold in (p.split(":") for p in spec.split(","))
    ]


def _parse_journey_pct_specs(spec):
    """Parse per-journey percentile overrides.

    Placeholder format until the CLI interface is decided:
    "pkg.mod:journey=50:100,90:200;pkg.mod:other=99:500"
    A pre-built {journey_spec: "50:100,..."} dict is also accepted.
    """
    if not spec:
        return {}
    if isinstance(spec, str):
        spec = dict(entry.rsplit("=", 1) for entry in spec.split(";") if entry)
    return {journey: _parse_pct_spec(pcts) for journey, pcts in spec.items()}

def _parse_transaction_pct_specs(spec):
    if not spec:
        return {}
    if isinstance(spec, str):
        spec = dict(entry.rsplit("=", 1) for entry in spec.split(";") if entry)
    results = {}
    for name, values in spec.items():
        pairs = (
            [(int(percentile), threshold) for percentile, threshold in values.items()]
            if isinstance(values, dict)
            else _parse_pct_spec(values)
        )
        results[name] = pairs
    return results

def _transaction_name(message):
    name = message.get("transaction")
    if name and name.startswith("__root__ :: "):
        name = name[len("__root__ :: "):]
    return name


class _StatsBucket:
    """Response time and throughput samples for a run, or one journey of a run."""

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
        self._journeys = defaultdict(_StatsBucket)
        self._transaction = defaultdict(_StatsBucket)
        self._pct_spec = _parse_pct_spec(opts.get("--benchmark-percentiles"))
        # TODO: decide whether a journey's percentiles should fully replace the
        # global spec (current behaviour) or be merged over it.
        self._journey_pct_specs = _parse_journey_pct_specs(
            opts.get("--journey-percentiles")
        )
        self._transaction_pct_specs = _parse_transaction_pct_specs(
            opts.get("--transaction-percentiles")
        )
        # Journeys with their own spec are always reported, even with no samples
        for journey in self._journey_pct_specs:
            self._journeys[journey]
        for transaction in self._transaction_pct_specs:
            self._transaction[transaction]

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
            for journey, bucket in self._journeys.items():
                if bucket.error_total:
                    self._logger.info(f"Total errors for {journey} :{bucket.error_total}")
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
        yield from self._journeys.values()
        yield from self._transaction.values()

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
            journey = self._journeys[message.get("journey")]
            transaction = _transaction_name(message)
            for bucket in (self._global, journey, self._transaction[transaction] if transaction else None):
                if bucket:
                    bucket.add_response(message["total_time"], message.get("download_size", 0))
            # if transaction:
            #     self._transaction[transaction].add_response(message["total_time"], message.get("download_size", 0))
        elif msg_type in ("error", "exception"):
            journey = self._journeys[message.get("journey")]
            transaction = _transaction_name(message)
            for bucket in (self._global, journey, self._transaction[transaction] if transaction else None):
                if bucket:
                    bucket.add_error()

    def pct_spec_for(self, journey=None, transaction=None):
        if transaction:
            return self._transaction_pct_specs.get(transaction, self._pct_spec)
        return self._journey_pct_specs.get(journey, self._pct_spec)

    @property
    def journey_stats(self):
        return dict(self._journeys)

    @property
    def percentiles_by_journey(self):
        return {
            journey: bucket.percentiles(self.pct_spec_for(journey=journey))
            for journey, bucket in self._journeys.items()
        }

    @property
    def percentiles_by_transaction(self):
        return {
            transaction: bucket.percentiles(self.pct_spec_for(transaction=transaction))
            for transaction, bucket in self._transaction.items()
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
