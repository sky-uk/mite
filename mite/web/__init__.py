from flask import Flask, Response

from .prometheus import PrometheusMetrics

app = Flask(__name__)

prometheus_metrics = PrometheusMetrics()


@app.route('/metrics')
def metrics():
    text = prometheus_metrics.format()
    return Response(text, mimetype='text/plain')
