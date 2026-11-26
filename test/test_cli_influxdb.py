from unittest.mock import MagicMock, patch

from mite.cli.influxdb import influxdb_init
from mite.stats import Counter, Gauge, extractor


def _patched_stat(stat_type_name, name="mite_fake_metric", labels=("transaction",)):
    stat_type = {"Counter": Counter, "Gauge": Gauge}[stat_type_name]
    return stat_type(name, lambda msg: True, extractor(list(labels)))


def test_influxdb_init_success():
    """Smoke test for point construction and the writer success path.
    load_stats_entry_points() is patched out (covered in test_stats.py), and
    the point fields are covered in test_influxdb_exporter.py;
    InfluxdbWriter is patched at its source module because influxdb_init
    imports it function-locally.
    """
    fake_stat = _patched_stat("Counter")

    future = MagicMock()
    future.result.return_value = None
    writer_instance = MagicMock()
    writer_instance.write_points.return_value = future

    with patch(
        "mite.cli.influxdb.load_stats_entry_points", return_value=[fake_stat]
    ), patch(
        "mite.stats_outputs.influxdb.InfluxdbWriter", return_value=writer_instance
    ) as writer_cls, patch("mite.stats_outputs.influxdb.influxdb_backend") as backend:
        exit_code = influxdb_init({"URL": ["influxdb3://h/db"]})

    assert exit_code == 0
    writer_cls.assert_called_once_with(backend.return_value)
    writer_instance.write_points.assert_called_once()
    points = writer_instance.write_points.call_args[0][0]
    assert len(points) == 1
    assert points[0].measurement == "mite_fake_metric"
    writer_instance.close.assert_called_once()


def test_influxdb_init_busy_writer_sets_exit_code():
    """write_points() returning None means the writer was busy - this must
    be surfaced as a non-zero exit code, not silently dropped."""
    fake_stat = _patched_stat("Gauge")

    writer_instance = MagicMock()
    writer_instance.write_points.return_value = None

    with patch(
        "mite.cli.influxdb.load_stats_entry_points", return_value=[fake_stat]
    ), patch("mite.stats_outputs.influxdb.InfluxdbWriter", return_value=writer_instance), patch(
        "mite.stats_outputs.influxdb.influxdb_backend"
    ):
        exit_code = influxdb_init({"URL": ["influxdb3://h/db"]})

    assert exit_code == 1
    writer_instance.close.assert_called_once()


def test_influxdb_init_writes_to_each_url():
    future = MagicMock()
    future.result.return_value = None
    writer_instance = MagicMock()
    writer_instance.write_points.return_value = future
    urls = ["influxdb1://a:8086/db", "influxdb3://b:8181/db"]

    with patch(
        "mite.cli.influxdb.load_stats_entry_points",
        return_value=[_patched_stat("Counter")],
    ), patch(
        "mite.stats_outputs.influxdb.InfluxdbWriter", return_value=writer_instance
    ), patch("mite.stats_outputs.influxdb.influxdb_backend") as backend:
        exit_code = influxdb_init({"URL": urls})

    assert exit_code == 0
    assert [str(c.args[0]) for c in backend.call_args_list] == urls


def test_influxdb_init_includes_custom_stat_types():
    # Before 4.0, init matched on the class name, so a custom Stat subclass
    # was silently left out; now it's written according to its dump type
    import dataclasses

    from mite.stats import GaugeAggregation, Stat

    @dataclasses.dataclass(frozen=True)
    class MaxGauge(Stat):
        aggregation_class = GaugeAggregation

    future = MagicMock()
    future.result.return_value = None
    writer_instance = MagicMock()
    writer_instance.write_points.return_value = future
    stat = MaxGauge("mite_peak", lambda msg: True, extractor(["test"]))

    with patch("mite.cli.influxdb.load_stats_entry_points", return_value=[stat]), patch(
        "mite.stats_outputs.influxdb.InfluxdbWriter", return_value=writer_instance
    ), patch("mite.stats_outputs.influxdb.influxdb_backend"):
        assert influxdb_init({"URL": ["influxdb3://h/db"]}) == 0

    (point,) = writer_instance.write_points.call_args[0][0]
    assert (point.measurement, point.tags, point.fields) == (
        "mite_peak", {"test": "__init__"}, {"value": 0.0},
    )
