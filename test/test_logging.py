import logging
import statistics
import sys
import types

import pytest

from mite.cli.test import _check_percentile_thresholds, benchmark_report
from mite.logoutput import (
    HttpStatsOutput,
    _parse_pct_spec,
    _StatsBucket,
    load_benchmark_percentiles,
)

TXN_A = "Login"
TXN_B = "Fetch profile"
NESTED = "Login :: Fetch token"


def test_journey_logging():
    optsTrue = {"--journey-logging": ""}

    optsFalse = {}

    h = HttpStatsOutput(optsTrue)
    assert h._journey_logging is True

    h = HttpStatsOutput(optsFalse)
    assert h._journey_logging is False


def _http(transaction, total_time, size=0, journey="pkg.mod:journey"):
    return {
        "type": "http_metrics",
        "journey": journey,
        "transaction": transaction,
        "total_time": total_time,
        "download_size": size,
    }


@pytest.fixture
def pct_config(monkeypatch):
    """Register `config` as an importable module attribute; return its spec."""

    def register(config):
        module = types.ModuleType("fake_benchmarks")
        module.CONFIG = config
        monkeypatch.setitem(sys.modules, "fake_benchmarks", module)
        return "fake_benchmarks:CONFIG"

    return register


@pytest.fixture
def txn_config(pct_config):
    """Configure TXN_A, TXN_B and NESTED so they're tracked per transaction."""
    return pct_config(
        {
            "*": {50: 0, 90: 100},
            TXN_A: {50: 0, 90: 100},
            TXN_B: {99: 650},
            NESTED: {50: 0},
        }
    )


def _stats(opts=None, messages=()):
    h = HttpStatsOutput({"--benchmark-percentiles": "50:0,90:100", **(opts or {})})
    for msg in messages:
        h.process_message(msg)
    h.finalise()
    return h


A_TIMES = [0.01 * i for i in range(1, 21)]
B_TIMES = [0.5, 0.6, 0.7]
MESSAGES = [_http(TXN_A, t, 10) for t in A_TIMES] + [
    _http(TXN_B, t, 5) for t in B_TIMES
]


def test_parse_pct_spec():
    assert _parse_pct_spec("50:0,90:200") == [(50, 0), (90, 200)]
    assert _parse_pct_spec(None) == []
    assert _parse_pct_spec("") == []


def test_parse_pct_spec_rejects_out_of_range_percentile():
    with pytest.raises(ValueError):
        _parse_pct_spec("100:0")


def test_load_inline_percentiles():
    assert load_benchmark_percentiles("50:0,90:200") == ([(50, 0), (90, 200)], {})
    assert load_benchmark_percentiles(None) == (
        [(50, 0), (90, 0), (98, 0), (99, 0)],
        {},
    )


def test_load_percentiles_from_spec(pct_config):
    spec = pct_config({"*": {50: 0, 90: 200}, TXN_A: {99: 500}})
    assert load_benchmark_percentiles(spec) == (
        [(50, 0), (90, 200)],
        {TXN_A: [(99, 500)]},
    )


def test_load_percentiles_from_spec_without_default(pct_config):
    spec = pct_config({TXN_A: {99: 500}})
    global_spec, _ = load_benchmark_percentiles(spec)
    assert global_spec == [(50, 0), (90, 0), (98, 0), (99, 0)]


@pytest.mark.parametrize(
    "config",
    [
        ["not", "a", "dict"],
        {TXN_A: "99:500"},
        {TXN_A: {0: 500}},
        {TXN_A: {90: -1}},
    ],
)
def test_load_percentiles_from_spec_rejects_bad_config(pct_config, config):
    with pytest.raises(ValueError):
        load_benchmark_percentiles(pct_config(config))


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


def test_stats_split_by_transaction(txn_config):
    h = _stats({"--benchmark-percentiles": txn_config}, MESSAGES)
    stats = h.transaction_stats
    assert set(stats) == {TXN_A, TXN_B, NESTED}
    assert stats[TXN_A].resp_times == A_TIMES
    assert stats[TXN_B].resp_time_max == 0.7
    assert stats[TXN_B].resp_time_mean == pytest.approx(0.6)

    by_transaction = h.percentiles_by_transaction
    assert by_transaction[TXN_A][1][2] == statistics.quantiles(A_TIMES, n=100)[89]


def test_requests_outside_a_transaction_only_count_globally(txn_config):
    h = _stats({"--benchmark-percentiles": txn_config}, MESSAGES + [_http(None, 0.9)])
    assert None not in h.transaction_stats
    assert h._req_total == len(MESSAGES) + 1
    assert h._resp_time_max == 0.9


def test_nested_transaction_is_its_own_group(txn_config):
    h = _stats(
        {"--benchmark-percentiles": txn_config}, [_http(TXN_A, 0.1), _http(NESTED, 0.2)]
    )
    stats = h.transaction_stats
    assert stats[TXN_A].resp_times == [0.1]
    assert stats[NESTED].resp_times == [0.2]


def test_same_transaction_combined_across_journeys(txn_config):
    h = _stats(
        {"--benchmark-percentiles": txn_config},
        [
            _http(TXN_A, 0.1, journey="pkg.mod:one"),
            _http(TXN_A, 0.2, journey="pkg.mod:two"),
        ]
    )
    assert h.transaction_stats[TXN_A].resp_times == [0.1, 0.2]


def test_only_configured_transactions_are_tracked(pct_config):
    spec = pct_config({"*": {50: 0, 90: 100}, TXN_B: {99: 650}})
    h = _stats({"--benchmark-percentiles": spec}, MESSAGES)
    assert set(h.transaction_stats) == {TXN_B}
    assert [(p, t) for p, t, _ in h.percentiles_by_transaction[TXN_B]] == [(99, 650)]
    assert h._req_total == len(MESSAGES)


def test_inline_config_tracks_no_transactions():
    h = _stats({"--benchmark-percentiles": "50:0,90:1"}, MESSAGES)
    assert h.transaction_stats == {}
    assert h.percentiles_by_transaction == {}


def test_errors_counted_per_transaction(txn_config):
    h = _stats(
        {"--benchmark-percentiles": txn_config},
        [{"type": "error", "journey": "pkg.mod:j", "transaction": TXN_A}],
    )
    assert h.error_total == 1
    assert h.transaction_stats[TXN_A].error_total == 1


def test_journey_logging_still_counts_errors_per_journey():
    h = _stats(
        {"--journey-logging": ""},
        [{"type": "error", "journey": "pkg.mod:j", "transaction": TXN_A}],
    )
    assert h._error_journeys == {"pkg.mod:j": 1}


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
        assert not _check_percentile_thresholds([(90, 100, None)], TXN_A)
    assert "Not enough samples" in caplog.text


def test_missing_transaction_is_reported(pct_config):
    spec = pct_config({"Never run": {90: 100}})
    h = _stats({"--benchmark-percentiles": spec}, MESSAGES)
    assert h.transaction_stats["Never run"].req_total == 0
    assert h.percentiles_by_transaction["Never run"] == [(90, 100, None)]


def test_threshold_breach_names_transaction(caplog):
    assert _check_percentile_thresholds([(90, 100, 0.2)], TXN_B)
    assert f"[{TXN_B}]" in caplog.text


def test_pct_formats_exact_index():
    h = HttpStatsOutput({})
    h._global.recent_resp_times.extend([0.1, 0.2, 0.3])
    assert h._pct(50) == "0.200000"


def _report(h):
    h._scenarios_completed_time = h._init_time + 1
    benchmark_report(
        h, (h.percentiles_list_resp_time_store, h.percentiles_by_transaction)
    )


def test_benchmark_report_per_transaction(pct_config, capsys):
    spec = pct_config({"*": {50: 0, 90: 100}, TXN_B: {99: 650}})
    h = _stats({"--benchmark-percentiles": spec}, MESSAGES)
    _report(h)
    out = capsys.readouterr().out
    assert "Per Transaction" in out
    assert f"| {TXN_B} " in out
    assert f"| {TXN_A} " not in out
    assert "99 %tile" in out


def test_benchmark_report_without_configured_transactions(capsys):
    h = _stats(messages=MESSAGES)
    _report(h)
    assert "Per Transaction" not in capsys.readouterr().out
