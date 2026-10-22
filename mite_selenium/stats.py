from mite.stats import Counter, Histogram, extractor, matcher_by_type

_PAGE_LOAD_METRICS = [
    ("dns_lookup_time", "seconds"),
    ("dom_interactive", "seconds"),
    ("js_onload_time", "seconds"),
    ("page_weight", "bytes"),
    ("render_time", "seconds"),
    ("tcp_time", "seconds"),
    ("tcp_time", "seconds"),
    ("time_to_first_byte", "seconds"),
    ("time_to_interactive", "seconds"),
    ("time_to_last_byte", "seconds"),
    ("tls_time", "seconds"),
    ("total_time", "seconds"),
]

_NETWORK_RESOURCE_METRICS = [
    ("dns_lookup_time", "seconds"),
    ("page_weight", "bytes"),
    ("tcp_time", "seconds"),
    ("time_to_first_byte", "seconds"),
    ("time_to_last_byte", "seconds"),
    ("tls_time", "seconds"),
    ("total_time", "seconds"),
]

_PAINT_METRICS = [("first_contentful_paint", "seconds"), ("first_paint", "seconds")]

_CUSTOM_METRICS = [
    ("js_execution_time", "seconds"),
]


def build_metrics(metrics, matcher, labels):
    histograms = []
    for metric, unit in metrics:
        bins = [0.0001, 0.001, 0.01, 0.05, 0.1, 0.2, 0.4, 0.8, 1, 2, 4, 8, 16, 32, 64]
        if unit == "bytes":
            bins = [b * 1000 for b in bins]

        histograms.append(
            Histogram(
                name=f"mite_{matcher}_{metric}_{unit}",
                matcher=matcher_by_type(f"{matcher}_metrics"),
                extractor=extractor(labels, metric),
                bins=bins,
            )
        )
    return histograms


STATS = (
    Counter(
        "mite_selenium_response_total",
        matcher_by_type("selenium_page_load_metrics"),
        extractor("test journey transaction".split()),
    ),
    *build_metrics(_PAGE_LOAD_METRICS, "selenium_page_load", ["transaction"]),
    *build_metrics(
        _NETWORK_RESOURCE_METRICS,
        "selenium_network_resource",
        ["transaction", "resource_path"],
    ),
    *build_metrics(_CUSTOM_METRICS, "selenium", ["transaction"]),
)
