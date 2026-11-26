import logging
from time import time_ns
from mite.exceptions import InfluxConfigError
from mite.stats import load_stats_entry_points
from mite.stats_outputs import OutputURL

logger = logging.getLogger(__name__)


def influxdb_init(opts):
    # Deferred, a module-level import here
    # would make every mite process pay the import
    # cost just to register this one subcommand.
    from mite.web.influxdb import InfluxdbWriter, influxdb_backend, influxdb_init_points

    all_stats = load_stats_entry_points()
    # An empty dump per stat gives each one's type and labels, so the points
    # use the same schema as real data (including custom stat types)
    dumps = [stat.aggregation_class(stat).dump() for stat in all_stats]
    points = influxdb_init_points(dumps, time_ns())

    urls = [OutputURL.parse(url) for url in opts["URL"]]
    exit_code = 0

    for url in urls:
        writer = InfluxdbWriter(influxdb_backend(url))
        try:
            future = writer.write_points(points)
            if future is None:
                raise InfluxConfigError(
                    f"InfluxDB writer for {url} was busy; init write was skipped"
                )
            future.result()
            logger.info(
                f"Initialized {len(all_stats)} metrics for {url}:"
            )
            for stat in all_stats:
                logger.info(f"  - {stat.name}")
        except Exception as e:
            logger.error(f"Error initializing {url}: {e}")
            exit_code = 1
        finally:
            writer.close()

    return exit_code
