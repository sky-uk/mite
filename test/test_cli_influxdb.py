from unittest.mock import MagicMock, patch

from mite.cli.influxdb import influxdb_init


class _StatMock:
    def __init__(self, name, extractor_labels):
        self.name = name
        self.extractor = MagicMock(labels=extractor_labels)


def _patched_stat(stat_type_name, name="mite_fake_metric", labels=("transaction",)):
    stat = _StatMock(name, labels)
    stat.__class__ = type(stat_type_name, (), {})
    return stat


def test_influxdb_init_success():
    """Smoke test for point construction and the writer success path.
    load_stats_entry_points() is patched out here, not exercised - its own
    behaviour (filtering, exception handling) is covered separately in
    test_stats.py. InfluxdbWriter is patched at its source module -
    influxdb_init imports it function-locally, so patching there is what
    actually takes effect.

    Covers the Counter/Gauge branches only; the Histogram branch (building
    percentile + cumulative fields and the '_summary' measurement name) and
    the multi-instance (--influxdb > 1) loop are knowingly left untested -
    a deliberate scope decision, not an oversight."""
    fake_stat = _patched_stat("Counter")

    future = MagicMock()
    future.result.return_value = None
    writer_instance = MagicMock()
    writer_instance.write_points.return_value = future

    with patch(
        "mite.cli.influxdb.load_stats_entry_points", return_value=[fake_stat]
    ), patch(
        "mite.web.influxdb.InfluxdbWriter", return_value=writer_instance
    ) as writer_cls:
        exit_code = influxdb_init({"--influxdb": "1"})

    assert exit_code == 0
    writer_cls.assert_called_once_with(suffix="")
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
    ), patch("mite.web.influxdb.InfluxdbWriter", return_value=writer_instance):
        exit_code = influxdb_init({"--influxdb": "1"})

    assert exit_code == 1
    writer_instance.close.assert_called_once()
