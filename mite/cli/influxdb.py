import importlib.metadata
import logging
from time import time_ns
from mite.web.influxdb import InfluxPoint, InfluxdbWriter
from mite.exceptions import InfluxConfigError

logger = logging.getLogger(__name__)


def influxdb_init(opts):
    all_stats = []
    for ep in importlib.metadata.entry_points(group="mite_stats"):
        try:
            all_stats.extend(ep.load())
        except Exception as e:
            logger.warning(f"Failed to load stats from entry point {ep.name}: {e}")

    points = []
    tns = time_ns()

    for stat in all_stats:
        name = stat.name
        labels = stat.extractor.labels
        tags = dict.fromkeys(labels, "__init__")
        stat_type = type(stat).__name__

        if stat_type in ("Counter", "Accumulator"):
            p = InfluxPoint(
                measurement=name,
                tags=tags,
                fields={"value": 0, "value_cumulative": 0},
                time_ns=tns,
            )
            points.append(p)

        elif stat_type == "Gauge":
            p = InfluxPoint(
                measurement=name,
                tags=tags,
                fields={"value": 0.0},
                time_ns=tns,
            )
            points.append(p)

        elif stat_type == "Histogram":
            fields = {}
            for pct in [50, 75, 90, 95, 99]:
                fields[f"p{pct}"] = 0.0
                fields[f"p{pct}_cumulative"] = 0.0
            fields.update({
                "sum": 0.0,
                "count": 0,
                "avg": 0.0,
                "sum_cumulative": 0.0,
                "count_cumulative": 0,
                "avg_cumulative": 0.0,
            })

            p = InfluxPoint(
                measurement=f"{name}_summary",
                tags=tags,
                fields=fields,
                time_ns=tns,
            )
            points.append(p)
    writer = InfluxdbWriter()
    try:
        future = writer.write_points(points)
        if future is None:
            raise InfluxConfigError("InfluxDB writer was busy; init write was skipped")
        future.result()
        logger.info(f"Initialized {len(all_stats)} metrics:")
        for stat in all_stats:
            logger.info(f"  - {stat.name}")
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
    finally:
        writer.close()
