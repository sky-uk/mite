import logging

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
