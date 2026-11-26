import unittest.mock as mock

import pytest

from mite.stats import Aggregator
from mite.stats_outputs import OutputURL, load_stats_outputs
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


class TestOutputURL:
    @pytest.mark.parametrize(
        "text, scheme, host, port, path, params",
        [
            ("prometheus://0.0.0.0:9301", "prometheus", "0.0.0.0", 9301, (), {}),
            ("prometheus://[::]:9301", "prometheus", "::", 9301, (), {}),
            ("prometheus://", "prometheus", None, None, (), {}),
            ("influxdb3://h:8181/db?buckets=true", "influxdb3", "h", 8181, ("db",), {"buckets": "true"}),
            ("influxdb2://h/org/bucket", "influxdb2", "h", None, ("org", "bucket"), {}),
        ],
    )
    def test_parse(self, text, scheme, host, port, path, params):
        url = OutputURL.parse(text)
        assert (url.scheme, url.host, url.port, url.path, dict(url.params)) == (
            scheme, host, port, path, params,
        )
        assert str(url) == text

    @pytest.mark.parametrize(
        "text, reason",
        [
            ("prometheus", "expected SCHEME://"),
            ("prometheus:9301", "expected SCHEME://"),
            ("prometheus://h:99999", "Port out of range"),
            ("x://h?a=1&a=2", "more than once"),
            ("x://h?a", "name=value pairs"),
            ("x://h#f", "fragment"),
        ],
    )
    def test_parse_rejects_invalid_urls(self, text, reason):
        with pytest.raises(ValueError, match=reason):
            OutputURL.parse(text)

    @pytest.mark.parametrize(
        "text", ["influxdb3://s3cr3t@h/db", "influxdb1://user:s3cr3t@h/db"]
    )
    def test_credentials_are_rejected_and_masked(self, text):
        with pytest.raises(ValueError, match="credentials") as error:
            OutputURL.parse(text)
        assert "s3cr3t" not in str(error.value)
        assert "//***@h/db" in str(error.value)

    def test_check(self):
        url = OutputURL.parse("x://h/a/b?known=1")
        url.check(paths=(("one",), ("one", "two")), params=("known",))
        with pytest.raises(ValueError, match="expected path /DATABASE"):
            url.check(paths=(("database",),), params=("known",))
        with pytest.raises(ValueError, match="unknown parameter known; allowed: none"):
            url.check(paths=(("a", "b"),))
        with pytest.raises(ValueError, match="expected path /$"):
            url.check(params=("known",))

    def test_flag(self):
        url = OutputURL.parse("x://h?on=true&off=false&bad=yes")
        assert url.flag("on") is True
        assert url.flag("off") is False
        assert url.flag("missing") is False
        with pytest.raises(ValueError, match="bad must be true or false"):
            url.flag("bad")


class TestLoadStatsOutputs:
    def test_no_urls_loads_nothing(self):
        assert load_stats_outputs([], {}) == []

    def test_each_url_creates_an_output_from_its_scheme(self):
        factory = mock.Mock(side_effect=lambda url, opts: url)
        opts = {}
        with _registry(fake=factory):
            outputs = load_stats_outputs(["fake://a", "fake://b/x"], opts)
        assert [str(o) for o in outputs] == ["fake://a", "fake://b/x"]
        assert all(c.args[1] is opts for c in factory.call_args_list)

    def test_unknown_output_lists_the_available_ones(self):
        with _registry(influxdb3=mock.Mock(), prometheus=mock.Mock()):
            with pytest.raises(ValueError, match="Unknown stats output nope; available: influxdb3, prometheus"):
                load_stats_outputs(["nope://h"], {})

    def test_repeated_output_is_rejected(self):
        with _registry(fake=mock.Mock()):
            with pytest.raises(ValueError, match="more than once: fake://h"):
                load_stats_outputs(["fake://h", "fake://h"], {})

    def test_outputs_already_created_are_closed_if_a_later_one_fails(self):
        created = mock.Mock()
        factory = mock.Mock(side_effect=[created, RuntimeError("no config")])
        with _registry(fake=factory):
            with pytest.raises(RuntimeError, match="no config"):
                load_stats_outputs(["fake://a", "fake://b"], {})
        created.close.assert_called_once()

    def test_first_party_outputs_are_registered(self):
        import importlib.metadata

        names = {ep.name for ep in importlib.metadata.entry_points(group="mite_stats_outputs")}
        assert {"influxdb1", "influxdb2", "influxdb3", "prometheus"} <= names


class TestInfluxDBOutput:
    ENV = {"INFLUXDB_TOKEN": "tok", "INFLUXDB_USERNAME": "user", "INFLUXDB_PASSWORD": "pw", "OTHER_TOKEN": "other"}

    def _backend(self, text, env=ENV):
        url = OutputURL.parse(text)
        with mock.patch.dict("os.environ", env, clear=True), mock.patch.object(
            influxdb, "_InfluxDBClientBackend"
        ) as v2, mock.patch.object(influxdb, "_InfluxDBClient3Backend") as v3:
            influxdb.influxdb_backend(url)
        (called,) = [b for b in (v2, v3) if b.called]
        return ("v3" if called is v3 else "v2"), called.call_args.kwargs

    @pytest.mark.parametrize(
        "text, client, kwargs",
        [
            ("influxdb3://h:8181/db", "v3", {"url": "http://h:8181", "token": "tok", "database": "db"}),
            ("influxdb3://h/db?tls=true&token_env=OTHER_TOKEN", "v3", {"url": "https://h", "token": "other", "database": "db"}),
            ("influxdb2://h:8086/org/bucket", "v2", {"url": "http://h:8086", "token": "tok", "org": "org", "bucket": "bucket"}),
            ("influxdb1://h:8086/db", "v2", {"url": "http://h:8086", "token": "user:pw", "org": "-", "bucket": "db/autogen"}),
            ("influxdb1://h/db/rp", "v2", {"url": "http://h", "token": "user:pw", "org": "-", "bucket": "db/rp"}),
            ("influxdb3://[::1]:8181/db", "v3", {"url": "http://[::1]:8181", "token": "tok", "database": "db"}),
        ],
    )
    def test_backend_from_url(self, text, client, kwargs):
        assert self._backend(text) == (client, kwargs)

    @pytest.mark.parametrize(
        "text, reason",
        [
            ("influxdb3:///db", "expected a host"),
            ("influxdb3://h", "expected path /DATABASE"),
            ("influxdb2://h/bucket", "expected path /ORG/BUCKET"),
            ("influxdb1://h/a/b/c", "expected path /DATABASE or /DATABASE/RETENTION_POLICY"),
            ("influxdb3://h/db?username_env=X", "unknown parameter username_env"),
            ("influxdb3://h/db?tls=yes", "tls must be true or false"),
        ],
    )
    def test_invalid_urls(self, text, reason):
        with pytest.raises(ValueError, match=reason):
            self._backend(text)

    def test_missing_credential_names_the_variable(self):
        with pytest.raises(influxdb.InfluxConfigError, match="MY_TOKEN is not set"):
            self._backend("influxdb3://h/db?token_env=MY_TOKEN")

    @pytest.mark.parametrize("text, include_buckets", [("influxdb3://h/db", False), ("influxdb3://h/db?buckets=true", True)])
    def test_output_buckets_parameter(self, text, include_buckets):
        with mock.patch.object(influxdb, "influxdb_backend") as backend, mock.patch.object(
            influxdb, "InfluxMetrics"
        ) as metrics:
            influxdb.influxdb_output(OutputURL.parse(text), {})
        metrics.assert_called_once_with(backend.return_value, include_buckets=include_buckets)


class TestPrometheusOutput:
    @pytest.mark.parametrize(
        "text, host, port",
        [("prometheus://", "127.0.0.1", 9301), ("prometheus://0.0.0.0:9400", "0.0.0.0", 9400), ("prometheus://[::]:9301", "::", 9301),
         # port 0 lets the OS choose a free port; it must not become the default
         ("prometheus://h:0", "h", 0), ("prometheus://:9400", "127.0.0.1", 9400)],
    )
    def test_serves_on_the_url_address(self, text, host, port):
        with mock.patch("mite.web.threading.Thread") as thread:
            prometheus_output(OutputURL.parse(text), {})
        assert thread.call_args.kwargs["kwargs"] == {"host": host, "port": port}
        thread.return_value.start.assert_called_once()

    def test_rejects_a_path_or_parameters(self):
        with pytest.raises(ValueError, match="expected path"):
            prometheus_output(OutputURL.parse("prometheus://h/metrics"), {})


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
