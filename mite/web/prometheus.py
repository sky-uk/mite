import logging

from .totals import CounterTotals, GaugeTotals, HistogramTotals, RunningTotals

logger = logging.getLogger(__name__)


def format_dict(d):
    return ",".join(
        [
            '%s="%s"' % (k, str(v).replace("\\", "\\\\").replace('"', '\\"'))
            for k, v in d.items()
        ]
    )


def _format_values(totals, prometheus_type):
    lines = [f"# TYPE {totals.name} {prometheus_type}"]
    for key, value in totals.values.items():
        labels = dict(zip(totals.labels, key))
        lines.append(f"{totals.name} {{{format_dict(labels)}}} {value}")
    return lines


def _format_histogram(totals):
    lines = [f"# TYPE {totals.name} histogram"]
    for key in sorted(totals.sums):
        bin_counts = totals.bin_counts.get(key, [0] * len(totals.bins))
        total_count = totals.total_counts.get(key, 0)
        labels = format_dict(dict(zip(totals.labels, key)))
        lines.extend(
            f'{totals.name}_bucket{{{labels},le="{bin_label:.6f}"}} {bin_count}'
            for bin_label, bin_count in zip(totals.bins, bin_counts)
        )
        lines.append(f'{totals.name}_bucket{{{labels},le="+Inf"}} {total_count}')
        lines.append(f"{totals.name}_sum{{{labels}}} {totals.sums[key]:.6f}")
        lines.append(f"{totals.name}_count{{{labels}}} {total_count}")
    return lines


def _format(totals):
    if isinstance(totals, HistogramTotals):
        return _format_histogram(totals)
    if isinstance(totals, GaugeTotals):
        return _format_values(totals, "gauge")
    if isinstance(totals, CounterTotals):
        return _format_values(totals, "counter")
    raise TypeError(f"no Prometheus format for {type(totals).__name__}")


class PrometheusMetrics:
    """The ``prometheus://`` stats output: running totals, rendered in the
    Prometheus text format by :meth:`format`."""

    def __init__(self):
        self.totals = RunningTotals()

    def send(self, dump):
        logger.debug("dump received by prometheus metrics: %s", dump)
        self.totals.update(dump)

    def close(self):
        pass

    def format(self):
        with self.totals.lock:
            blocks = ["\n".join(_format(totals)) for totals in self.totals.stats.values()]
        return "\n\n".join(blocks)
