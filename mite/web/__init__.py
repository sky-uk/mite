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


def prometheus_output(spec, opts):
    """``mite_stats_outputs`` factory: serve stats at ``/metrics`` on
    ``--web-address`` for Prometheus to scrape."""
    if spec.instance is not None:
        raise ValueError(
            f"Stats output {spec}: prometheus doesn't support instances"
        )
    start_web_in_thread(opts["--web-address"])
    return prometheus_metrics


def start_web_in_thread(address):
    kwargs = {"port": 9301}
    if address.startswith("["):
        # IPV6 [host]:port
        if "]:" in address:
            host, port = address.split("]:")
            kwargs["host"] = host[1:]
            kwargs["port"] = int(port)
        else:
            kwargs["host"] = address[1:-1]
    elif address.count(":") == 1:
        host, port = address.split(":")
        kwargs["host"] = host
        kwargs["port"] = int(port)
    else:
        kwargs["host"] = address
    t = threading.Thread(target=app.run, name="mite.web", kwargs=kwargs)
    t.daemon = True
    t.start()
