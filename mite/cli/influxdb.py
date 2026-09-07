import importlib.metadata
import logging
import os
from time import time_ns

from influxdb_client_3 import InfluxDBClient3, Point

logger = logging.getLogger(__name__)


def influxdb_init(opts):
    host = os.getenv("INFLUXDB_HOST")
    database = os.getenv("INFLUXDB_DATABASE")
    token = os.getenv("INFLUXDB_TOKEN")

    if not token or not host or not database:
        raise ValueError("INFLUXDB_HOST, INFLUXDB_DATABASE, and INFLUXDB_TOKEN variables are empty")

    logger.info(f"Connecting to {host}, database: {database}")

    client = InfluxDBClient3(host=host, token=token, database=database)

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
            p = Point(name)
            for k, v in tags.items():
                p.tag(k, v)
            p.field("value", 0)
            p.field("value_cumulative", 0)
            p.time(tns)
            points.append(p)

        elif stat_type == "Gauge":
            p = Point(name)
            for k, v in tags.items():
                p.tag(k, v)
            p.field("value", 0.0)
            p.time(tns)
            points.append(p)

        elif stat_type == "Histogram":
            p = Point(f"{name}_summary")
            for k, v in tags.items():
                p.tag(k, v)
            for pct in [50, 75, 90, 95, 99]:
                p.field(f"p{pct}", 0.0)
                p.field(f"p{pct}_cumulative", 0.0)
            p.field("sum", 0.0)
            p.field("count", 0)
            p.field("avg", 0.0)
            p.field("sum_cumulative", 0.0)
            p.field("count_cumulative", 0)
            p.field("avg_cumulative", 0.0)
            p.time(tns)
            points.append(p)

    try:
        client.write(points)
        logger.info(f"Initialized {len(all_stats)} metrics:")
        for stat in all_stats:
            logger.info(f"  - {stat.name}")
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1
