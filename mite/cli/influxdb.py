import logging
from time import time_ns
from mite.exceptions import InfluxConfigError
from mite.stats import load_stats_entry_points

logger = logging.getLogger(__name__)


def influxdb_init(opts):
    # Deferred, a module-level import here
    # would make every mite process pay the import
    # cost just to register this one subcommand.
    from mite.web.influxdb import InfluxPoint, InfluxdbWriter

    all_stats = load_stats_entry_points()

    points = []
    tns = time_ns()

    for stat in all_stats:
        name = stat.name
        labels = stat.extractor.labels
        tags = dict.fromkeys(labels, "__init__")
        stat_type = type(stat).__name__

        if stat_type in ("Counter", "Accumulator"):
            points.append(
                InfluxPoint(
                    measurement=name,
                    tags=tags,
                    fields={"value": 0, "value_cumulative": 0},
                    time_ns=tns,
                )
            )

        elif stat_type == "Gauge":
            points.append(
                InfluxPoint(
                    measurement=name,
                    tags=tags,
                    fields={"value": 0.0},
                    time_ns=tns,
                )
            )

        elif stat_type == "Histogram":
            fields = {}
            for pct in [50, 75, 90, 95, 99]:
                fields[f"p{pct}"] = 0.0
                fields[f"p{pct}_cumulative"] = 0.0
            fields.update(
                {
                    "sum": 0.0,
                    "count": 0,
                    "avg": 0.0,
                    "sum_cumulative": 0.0,
                    "count_cumulative": 0,
                    "avg_cumulative": 0.0,
                }
            )
            points.append(
                InfluxPoint(
                    measurement=f"{name}_summary",
                    tags=tags,
                    fields=fields,
                    time_ns=tns,
                )
            )

    influxdb_count = int(opts.get("--influxdb") or 1)
    exit_code = 0

    for i in range(influxdb_count):
        suffix = "" if i == 0 else f"_{i + 1}"
        writer = InfluxdbWriter(suffix=suffix)
        try:
            future = writer.write_points(points)
            if future is None:
                raise InfluxConfigError(
                    f"InfluxDB writer{suffix} was busy; init write was skipped"
                )
            future.result()
            logger.info(
                f"Initialized {len(all_stats)} metrics for instance{suffix or ' (default)'}:"
            )
            for stat in all_stats:
                logger.info(f"  - {stat.name}")
        except Exception as e:
            logger.error(f"Error initializing instance{suffix}: {e}")
            exit_code = 1
        finally:
            writer.close()

    return exit_code
