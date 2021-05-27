import os

from mite.stats import Counter, Histogram, extractor, matcher_by_type

STATS = (
    Counter(
        name="mite_finagle_response_total",
        matcher=matcher_by_type("finagle_metrics"),
        extractor=extractor(("test", "journey", "transaction", "function", "had_error")),
    ),
    Histogram(
        name="mite_finagle_response_time_seconds",
        matcher=matcher_by_type("finagle_metrics"),
        extractor=extractor(["transaction"], "total_time"),
        bins=[
            float(x)
            for x in os.environ.get(
                "MITE_FINAGLE_HISTOGRAM_BUCKETS",
                "0.0001,0.001,0.01,0.05,0.1,0.2,0.4,0.8,1,2,4,8",
            ).split(",")
        ],
    ),
)
