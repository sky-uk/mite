import unittest.mock as mock

import pytest

from mite.stats import Aggregator
from mite.stats_outputs import OutputSpec, load_stats_outputs
from mite.web import influxdb, prometheus_output


class _EntryPoint:
    def __init__(self, name, factory):
        self.name = name
        self._factory = factory

    def load(self):
        return self._factory


def _registry(**factories):
    return mock.patch(
        "importlib.metadata.entry_points",
        return_value=[_EntryPoint(name, f) for name, f in factories.items()],
    )


class TestOutputSpec:
    @pytest.mark.parametrize(
        "spec, name, instance, suffix",
        [
            ("influxdb", "influxdb", None, ""),
            ("influxdb:2", "influxdb", "2", "_2"),
            ("influxdb:secondary", "influxdb", "secondary", "_SECONDARY"),
            ("my_output:eu_west_1", "my_output", "eu_west_1", "_EU_WEST_1"),
        ],
    )
    def test_parse(self, spec, name, instance, suffix):
        parsed = OutputSpec.parse(spec)
        assert (parsed.name, parsed.instance, parsed.suffix) == (name, instance, suffix)
        assert str(parsed) == spec

    @pytest.mark.parametrize("spec", ["", "influxdb:", ":2", "influx-db", "a:b:c", "a:b c"])
    def test_parse_rejects_invalid_specs(self, spec):
        with pytest.raises(ValueError, match="Invalid stats output"):
            OutputSpec.parse(spec)


class TestLoadStatsOutputs:
    def test_no_specs_loads_nothing(self):
        assert load_stats_outputs([], {}) == []

    def test_each_spec_creates_an_output_from_its_factory(self):
        factory = mock.Mock(side_effect=lambda spec, opts: spec)
        opts = {"--web-address": "x"}
        with _registry(fake=factory):
            outputs = load_stats_outputs(["fake", "fake:2", "fake:other"], opts)
        assert [str(o) for o in outputs] == ["fake", "fake:2", "fake:other"]
        assert all(c.args[1] is opts for c in factory.call_args_list)

    def test_unknown_output_lists_the_available_ones(self):
        with _registry(influxdb=mock.Mock(), prometheus=mock.Mock()):
            with pytest.raises(ValueError, match="Unknown stats output nope; available: influxdb, prometheus"):
                load_stats_outputs(["nope"], {})

    def test_repeated_output_is_rejected(self):
        with _registry(fake=mock.Mock()):
            with pytest.raises(ValueError, match="more than once: fake:2"):
                load_stats_outputs(["fake:2", "fake:2"], {})

    def test_outputs_already_created_are_closed_if_a_later_one_fails(self):
        created = mock.Mock()
        factory = mock.Mock(side_effect=[created, RuntimeError("no config")])
        with _registry(fake=factory):
            with pytest.raises(RuntimeError, match="no config"):
                load_stats_outputs(["fake", "fake:2"], {})
        created.close.assert_called_once()

    def test_first_party_outputs_are_registered(self):
        import importlib.metadata

        names = {ep.name for ep in importlib.metadata.entry_points(group="mite_stats_outputs")}
        assert {"influxdb", "prometheus"} <= names


class TestFirstPartyOutputs:
    @pytest.mark.parametrize(
        "spec, env, suffix, include_buckets",
        [
            ("influxdb", {}, "", False),
            ("influxdb:2", {"INFLUXDB_INCLUDE_BUCKETS_2": "true"}, "_2", True),
            # another instance's setting doesn't apply
            ("influxdb", {"INFLUXDB_INCLUDE_BUCKETS_2": "true"}, "", False),
        ],
    )
    def test_influxdb_output(self, spec, env, suffix, include_buckets):
        with mock.patch.dict("os.environ", env, clear=True), mock.patch.object(
            influxdb, "InfluxMetrics"
        ) as metrics:
            influxdb.influxdb_output(OutputSpec.parse(spec), {})
        metrics.assert_called_once_with(include_buckets=include_buckets, suffix=suffix)

    def test_prometheus_output_rejects_instances(self):
        with pytest.raises(ValueError, match="doesn't support instances"):
            prometheus_output(OutputSpec.parse("prometheus:2"), {})


def test_test_mode_sends_to_all_outputs_through_one_aggregator():
    from mite.cli import test as cli_test

    outputs = [mock.Mock(), mock.Mock()]
    receiver = cli_test.DirectReciever()
    opts = {
        "--collector-dir": "unused",
        "--collector-roll": "1",
        "--recorder-dir": "unused",
        "--message-processors": "",
        "--stats-output": ["a", "b"],
    }
    with mock.patch.object(cli_test, "Collector"), mock.patch.object(
        cli_test, "Recorder"
    ), mock.patch.object(cli_test, "load_stats_outputs", return_value=outputs) as load:
        processors = cli_test._setup_msg_processors(receiver, opts)

    load.assert_called_once_with(["a", "b"], opts)
    aggregators = [p for p in processors if isinstance(p, Aggregator)]
    assert len(aggregators) == 1
    assert aggregators[0]._senders == outputs


def test_mite_stats_sends_to_the_socket_and_flushes_on_shutdown():
    from mite.cli import stats as cli_stats

    receiver = mock.Mock()

    async def run():
        receiver.add_listener.call_args[0][0]({"type": "txn", "test": "t"})
        raise KeyboardInterrupt

    receiver.run = run
    sender = mock.Mock()
    opts = {"--stats-include-processors": "mite", "--stats-exclude-processors": None}
    with mock.patch.object(cli_stats, "_create_receiver", return_value=receiver), \
            mock.patch.object(cli_stats, "_create_sender", return_value=sender):
        cli_stats.stats(opts)

    dump = sender.send.call_args[0][0]
    txn = next(d for d in dump if d["name"] == "mite_transaction_total")
    assert sum(txn["metrics"].values()) == 1
    sender.close.assert_called_once()
