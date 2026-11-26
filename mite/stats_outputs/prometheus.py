import logging
import threading

from flask import Flask, Response

from .cumulative import CumulativeCounter, CumulativeGauge, CumulativeHistogram, CumulativeStats

logger = logging.getLogger(__name__)


def format_dict(d):
    return ",".join(
        [
            '%s="%s"' % (k, str(v).replace("\\", "\\\\").replace('"', '\\"'))
            for k, v in d.items()
        ]
    )


def _format_values(cumulative, prometheus_type):
    lines = [f"# TYPE {cumulative.name} {prometheus_type}"]
    for key, value in cumulative.values.items():
        labels = dict(zip(cumulative.labels, key))
        lines.append(f"{cumulative.name} {{{format_dict(labels)}}} {value}")
    return lines


def _format_histogram(cumulative):
    lines = [f"# TYPE {cumulative.name} histogram"]
    for key in sorted(cumulative.sums):
        bin_counts = cumulative.bin_counts.get(key, [0] * len(cumulative.bins))
        total_count = cumulative.total_counts.get(key, 0)
        labels = format_dict(dict(zip(cumulative.labels, key)))
        lines.extend(
            f'{cumulative.name}_bucket{{{labels},le="{bin_label:.6f}"}} {bin_count}'
            for bin_label, bin_count in zip(cumulative.bins, bin_counts)
        )
        lines.append(f'{cumulative.name}_bucket{{{labels},le="+Inf"}} {total_count}')
        lines.append(f"{cumulative.name}_sum{{{labels}}} {cumulative.sums[key]:.6f}")
        lines.append(f"{cumulative.name}_count{{{labels}}} {total_count}")
    return lines


def _format(cumulative):
    if isinstance(cumulative, CumulativeHistogram):
        return _format_histogram(cumulative)
    if isinstance(cumulative, CumulativeGauge):
        return _format_values(cumulative, "gauge")
    if isinstance(cumulative, CumulativeCounter):
        return _format_values(cumulative, "counter")
    raise TypeError(f"no Prometheus format for {type(cumulative).__name__}")


class PrometheusMetrics:
    """The ``prometheus://`` stats output: cumulative values, rendered in the
    Prometheus text format by :meth:`format`."""

    def __init__(self):
        self.cumulative = CumulativeStats()

    def send(self, dump):
        logger.debug("dump received by prometheus metrics: %s", dump)
        self.cumulative.update(dump)

    def close(self):
        pass

    def format(self):
        with self.cumulative.lock:
            blocks = ["\n".join(_format(stat)) for stat in self.cumulative.stats.values()]
        return "\n\n".join(blocks)


def _create_app(metrics):
    app = Flask(__name__)
    # FIXME: the goal of this line is to cut down on the once-per-second server
    # log line from the prometheus scrape.  But I don't think it works...
    app.logger.setLevel(logging.WARNING)

    @app.route('/metrics')
    def serve_metrics():
        return Response(metrics.format(), mimetype='text/plain')

    return app


def prometheus_output(url, opts):
    """``mite_stats_outputs`` factory for ``prometheus://[HOST][:PORT]``:
    serve stats at ``/metrics`` on HOST:PORT (default 127.0.0.1:9301) for
    Prometheus to scrape."""
    url.check()
    host = "127.0.0.1" if url.host is None else url.host
    port = 9301 if url.port is None else url.port
    metrics = PrometheusMetrics()
    thread = threading.Thread(
        target=_create_app(metrics).run,
        name=f"mite prometheus {host}:{port}",
        kwargs={"host": host, "port": port},
        daemon=True,
    )
    thread.start()
    return metrics
