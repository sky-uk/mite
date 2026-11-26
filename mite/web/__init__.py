import logging
import threading

from flask import Flask, Response

from .prometheus import PrometheusMetrics

app = Flask(__name__)
# FIXME: the goal of this line is to cut down on the once-per-second server
# log line from the prometheus scrape.  But I don't think it works...
app.logger.setLevel(logging.WARNING)

prometheus_metrics = PrometheusMetrics()


@app.route('/metrics')
def metrics():
    text = prometheus_metrics.format()
    return Response(text, mimetype='text/plain')


def prometheus_output(url, opts):
    """``mite_stats_outputs`` factory for ``prometheus://[HOST][:PORT]``:
    serve stats at ``/metrics`` on HOST:PORT (default 127.0.0.1:9301) for
    Prometheus to scrape. Only one per process."""
    url.check()
    host = "127.0.0.1" if url.host is None else url.host
    port = 9301 if url.port is None else url.port
    thread = threading.Thread(
        target=app.run, name="mite.web", kwargs={"host": host, "port": port}, daemon=True
    )
    thread.start()
    return prometheus_metrics
