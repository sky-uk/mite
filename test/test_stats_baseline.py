"""Pin the stats pipeline's output for a fixed message stream, so refactoring
can't silently change what reaches the exporters.

After an intended change, regenerate the expected output with:

    MITE_UPDATE_STATS_EXPECTED=1 pytest test/test_stats_baseline.py
"""

import ast
import dataclasses
import os
import pprint
import unittest.mock as mock
from concurrent.futures import Future
from pathlib import Path

import pytest

from mite.cli import influxdb as cli_influxdb
from mite.stats import Stats, load_stats_entry_points
from mite.web import influxdb
from mite.web.prometheus import PrometheusMetrics

EXPECTED_FILE = Path(__file__).parent / "data" / "stats_expected_output.txt"

# Fixed so the output doesn't depend on which optional plugins are installed
PROCESSORS = ["mite", "mite_http", "mite_http_extended"]
FIXED_TIME_NS = 1_700_000_000_000_000_000


def _msg(type, transaction, **fields):
    return {
        "type": type,
        "test": "proj.file:scenario",
        "journey": "proj.file:journey",
        "transaction": transaction,
        **fields,
    }


def _controller_report(actual, required, num_runners):
    return {
        "type": "controller_report",
        "test": "proj.file:scenario",
        "actual": actual,
        "required": required,
        "num_runners": num_runners,
    }


ERROR = dict(location="proj/file.py:10", ex_type="HTTPError", message="500")
HTTP = dict(method="GET", response_code=200)

ROUNDS = [
    [
        _msg("txn", "login", had_error=False),
        _msg("txn", "login", had_error=True),
        _msg("error", "login", **ERROR),
        _msg("exception", "search", **ERROR),
        _controller_report({1: 5, 2: 3}, {1: 5, 2: 4}, 2),
        _msg("http_metrics", "login", **HTTP, total_time=0.003, dns_time=0.0005,
             connect_time=0.001, tls_time=0.002, download_size=512, upload_size=0),
        # connect/tls of 0 (reused connection) are skipped by the extended stats
        _msg("http_metrics", "login", **HTTP, total_time=0.15, connect_time=0,
             tls_time=0, download_size=2048, upload_size=300),
        # older senders omit the extended fields entirely
        _msg("http_metrics", "search", **HTTP, total_time=1.5),
    ],
    [
        _msg("txn", "search", had_error=False),
        _controller_report({1: 6, 2: 3}, {1: 6, 2: 4}, 3),
        _msg("http_metrics", "search", method="GET", response_code=504, total_time=20.0),
    ],
]


def _dumps():
    stats = Stats(sender=lambda _: None, include=PROCESSORS)
    dumps = []
    for messages in ROUNDS:
        for msg in messages:
            stats.process(msg)
        dumps.append(sorted(stats.dump(), key=lambda s: s["name"]))
    return dumps


def _prometheus(dumps):
    metrics = PrometheusMetrics()
    for dump in dumps:
        metrics.process(dump)
    return metrics.format().splitlines()


def _sorted_points(write_calls):
    points = (dataclasses.asdict(p) for call in write_calls for p in call.args[0])
    return sorted(points, key=repr)


def _influx(dumps, include_buckets):
    backend = mock.Mock()
    with mock.patch.object(influxdb, "_create_influx_backend", return_value=backend), \
            mock.patch.object(influxdb, "time_ns", return_value=FIXED_TIME_NS), \
            mock.patch.object(influxdb.InfluxMetrics, "MIN_FLUSH_INTERVAL", 1e9):
        metrics = influxdb.InfluxMetrics(include_buckets=include_buckets)
        for dump in dumps:
            metrics.process(dump)
        metrics.close()  # everything is buffered until close
    return _sorted_points(backend.write_points.call_args_list)


def _influx_init():
    done = Future()
    done.set_result(None)
    writer = mock.Mock()
    writer.return_value.write_points.return_value = done
    stats = load_stats_entry_points(include=PROCESSORS)
    with mock.patch.object(influxdb, "InfluxdbWriter", writer), \
            mock.patch.object(cli_influxdb, "load_stats_entry_points", return_value=stats), \
            mock.patch.object(cli_influxdb, "time_ns", return_value=FIXED_TIME_NS):
        assert cli_influxdb.influxdb_init({"--influxdb": "1"}) == 0
    return _sorted_points(writer.return_value.write_points.call_args_list)


@pytest.fixture(scope="module")
def actual():
    dumps = _dumps()
    output = {
        "dumps": dumps,
        "prometheus": _prometheus(dumps),
        "influx": _influx(dumps, include_buckets=False),
        "influx_with_buckets": _influx(dumps, include_buckets=True),
        "influx_init": _influx_init(),
    }
    if os.environ.get("MITE_UPDATE_STATS_EXPECTED") == "1":
        EXPECTED_FILE.parent.mkdir(exist_ok=True)
        EXPECTED_FILE.write_text(pprint.pformat(output, width=100) + "\n")
    return output


@pytest.fixture(scope="module")
def expected():
    return ast.literal_eval(EXPECTED_FILE.read_text())


@pytest.mark.parametrize(
    "section", ["dumps", "prometheus", "influx", "influx_with_buckets", "influx_init"]
)
def test_stats_output_unchanged(actual, expected, section):
    assert actual[section] == expected[section]
