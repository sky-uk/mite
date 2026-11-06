import logging
import statistics
import sys
import types

import pytest

from mite.cli.test import _check_percentile_thresholds, benchmark_report
from mite.logoutput import (
    HttpStatsOutput,
    _parse_journey_pct_specs,
    _parse_pct_spec,
    _parse_transaction_pct_specs,
    _StatsBucket,
)

JOURNEY_A = "pkg.mod:journey_a"
JOURNEY_B = "pkg.mod:journey_b"
TRANSACTION_A = "checkout"
TRANSACTION_B = "checkout :: payment"


def test_journey_logging():
    optsTrue = {"--journey-logging": ""}

    optsFalse = {}

    h = HttpStatsOutput(optsTrue)
    assert h._journey_logging is True

    h = HttpStatsOutput(optsFalse)
    assert h._journey_logging is False


def _http(journey, total_time, size=0, transaction=None):
    return {
        "type": "http_metrics",
        "journey": journey,
        "total_time": total_time,
        "download_size": size,
        "transaction": transaction,
    }


def _stats(opts=None, messages=()):
    h = HttpStatsOutput({"--benchmark-percentiles": "50:0,90:100", **(opts or {})})
    for msg in messages:
        h.process_message(msg)
    h.finalise()
    return h


def _percentile_results(stats):
    return (
        stats.percentiles_list_resp_time_store,
        stats.percentiles_by_journey,
        stats.percentiles_by_transaction,
    )


A_TIMES = [0.01 * i for i in range(1, 21)]
B_TIMES = [0.5, 0.6, 0.7]
MESSAGES = [_http(JOURNEY_A, t, 10) for t in A_TIMES] + [
    _http(JOURNEY_B, t, 5) for t in B_TIMES
]


def test_parse_pct_spec():
    assert _parse_pct_spec("50:0,90:200") == [(50, 0), (90, 200)]
    assert _parse_pct_spec(None) == []
    assert _parse_pct_spec("") == []


def test_parse_journey_pct_specs():
    assert _parse_journey_pct_specs(f"{JOURNEY_A}=50:100;{JOURNEY_B}=99:500") == {
        JOURNEY_A: [(50, 100)],
        JOURNEY_B: [(99, 500)],
    }
    assert _parse_journey_pct_specs({JOURNEY_A: "90:1"}) == {JOURNEY_A: [(90, 1)]}
    assert _parse_journey_pct_specs(None) == {}


def test_parse_transaction_pct_specs_inline():
    assert _parse_transaction_pct_specs(
        f"{TRANSACTION_A}=50:100,90:200;{TRANSACTION_B}=99:500"
    ) == {
        TRANSACTION_A: [(50, 100), (90, 200)],
        TRANSACTION_B: [(99, 500)],
    }


@pytest.mark.parametrize(
    ("parser", "attribute", "expected"),
    [
        (
            _parse_journey_pct_specs,
            "journey_specs",
            {JOURNEY_A: [(50, 0), (99, 400)]},
        ),
        (
            _parse_transaction_pct_specs,
            "transaction_specs",
            {TRANSACTION_A: [(50, 0), (99, 400)]},
        ),
    ],
)
def test_parse_named_pct_specs_from_import(parser, attribute, expected, monkeypatch):
    module = types.ModuleType("test_benchmark_specs")
    module.__dict__.update(
        {
            "journey_specs": {JOURNEY_A: "50:0,99:400"},
            "transaction_specs": {TRANSACTION_A: "50:0,99:400"},
        }
    )
    monkeypatch.setitem(sys.modules, module.__name__, module)

    assert parser(f"@{module.__name__}:{attribute}") == expected


def test_finalise_includes_last_period():
    h = _stats(messages=MESSAGES)
    assert len(h._global.resp_times) == len(A_TIMES) + len(B_TIMES)
    assert h._global.recent_resp_times == []


def test_global_stats_unchanged():
    h = _stats(messages=MESSAGES)
    all_times = A_TIMES + B_TIMES
    quantiles = statistics.quantiles(all_times, n=100)
    assert h.percentiles_list_resp_time_store == [
        (50, 0, quantiles[49]),
        (90, 100, quantiles[89]),
    ]
    assert h.mean_resp_time == pytest.approx(statistics.fmean(all_times))
    assert h._resp_time_min == min(all_times)
    assert h._resp_time_max == max(all_times)
    assert h._req_total == len(all_times)
    assert h._data_transferred == 10 * len(A_TIMES) + 5 * len(B_TIMES)


def test_stats_split_by_journey():
    h = _stats(messages=MESSAGES)
    stats = h.journey_stats
    assert set(stats) == {JOURNEY_A, JOURNEY_B}
    assert stats[JOURNEY_A].resp_times == A_TIMES
    assert stats[JOURNEY_B].resp_time_max == 0.7
    assert stats[JOURNEY_B].resp_time_mean == pytest.approx(0.6)

    by_journey = h.percentiles_by_journey
    assert by_journey[JOURNEY_A][1][2] == statistics.quantiles(A_TIMES, n=100)[89]


def test_journey_spec_replaces_global_spec():
    h = _stats({"--journey-percentiles": f"{JOURNEY_B}=99:650"}, MESSAGES)
    by_journey = h.percentiles_by_journey
    assert [(p, t) for p, t, _ in by_journey[JOURNEY_A]] == [(50, 0), (90, 100)]
    assert [(p, t) for p, t, _ in by_journey[JOURNEY_B]] == [(99, 650)]


def test_transaction_stats_and_percentiles():
    messages = [
        _http(JOURNEY_A, 0.1, transaction=f"__root__ :: {TRANSACTION_A}"),
        _http(JOURNEY_B, 0.2, transaction=f"__root__ :: {TRANSACTION_A}"),
        _http(JOURNEY_A, 0.8, transaction=f"__root__ :: {TRANSACTION_B}"),
    ]
    h = _stats(
        {"--transaction-percentiles": f"{TRANSACTION_A}=50:0,90:150"},
        messages,
    )

    assert set(h.percentiles_by_transaction) == {TRANSACTION_A, TRANSACTION_B}
    bucket = h._transaction[TRANSACTION_A]
    assert bucket.resp_times == [0.1, 0.2]
    assert bucket.req_total == 2
    assert h.percentiles_by_transaction[TRANSACTION_A] == [
        (50, 0, statistics.quantiles([0.1, 0.2], n=100)[49]),
        (90, 150, statistics.quantiles([0.1, 0.2], n=100)[89]),
    ]


def test_errors_counted_per_transaction():
    h = _stats(
        messages=[
            {
                "type": "error",
                "journey": JOURNEY_A,
                "transaction": f"__root__ :: {TRANSACTION_A}",
            }
        ]
    )

    assert h.error_total == 1
    assert h._transaction[TRANSACTION_A].error_total == 1


def test_transaction_threshold_breach_names_transaction(caplog):
    results = [(90, 100, 0.2)]
    assert _check_percentile_thresholds(results, transaction=TRANSACTION_A)
    assert f"[{TRANSACTION_A}]" in caplog.text


def test_errors_counted_per_journey():
    h = _stats(messages=[{"type": "error", "journey": JOURNEY_A}])
    assert h.error_total == 1
    assert h.journey_stats[JOURNEY_A].error_total == 1


@pytest.mark.parametrize("samples", [[], [0.1]])
def test_small_samples(samples):
    bucket = _StatsBucket()
    for s in samples:
        bucket.add_response(s)
    bucket.flush(elapsed=1)
    assert bucket.percentiles([(50, 0), (90, 100)]) == [(50, 0, None), (90, 100, None)]
    assert bucket.resp_time_stdev is None
    assert bucket.resp_time_within_stdev is None
    assert bucket.req_sec_stdev is None


def test_small_sample_threshold_warns_not_fails(caplog):
    with caplog.at_level(logging.WARNING):
        assert not _check_percentile_thresholds([(90, 100, None)], JOURNEY_A)
    assert "Not enough samples" in caplog.text


def test_missing_journey_is_reported():
    h = _stats({"--journey-percentiles": "pkg.mod:never_run=90:100"}, MESSAGES)
    assert h.journey_stats["pkg.mod:never_run"].req_total == 0
    assert h.percentiles_by_journey["pkg.mod:never_run"] == [(90, 100, None)]


def test_threshold_breach_names_journey(caplog):
    assert _check_percentile_thresholds([(90, 100, 0.2)], JOURNEY_B)
    assert f"[{JOURNEY_B}]" in caplog.text


def test_pct_formats_exact_index():
    h = HttpStatsOutput({})
    h._global.recent_resp_times.extend([0.1, 0.2, 0.3])
    assert h._pct(50) == "0.200000"


def test_benchmark_report_per_journey(capsys):
    h = _stats({"--journey-percentiles": f"{JOURNEY_B}=99:650"}, MESSAGES)
    h._scenarios_completed_time = int(h._init_time) + 1
    benchmark_report(h, _percentile_results(h))
    out = capsys.readouterr().out
    assert "Per Journey" in out
    assert "| journey_a " in out and "| journey_b " in out
    assert JOURNEY_A not in out
    assert "99 %tile" in out


def test_benchmark_report_per_transaction(capsys):
    messages = [
        _http(JOURNEY_A, 0.1, transaction=f"__root__ :: {TRANSACTION_A}"),
        _http(JOURNEY_A, 0.2, transaction=f"__root__ :: {TRANSACTION_A}"),
    ]
    h = _stats(
        {"--transaction-percentiles": f"{TRANSACTION_A}=99:500"},
        messages,
    )
    h._scenarios_completed_time = int(h._init_time) + 1

    benchmark_report(h, _percentile_results(h))

    out = capsys.readouterr().out
    assert "Per Transaction" in out
    assert TRANSACTION_A in out
    assert "99 %tile" in out
