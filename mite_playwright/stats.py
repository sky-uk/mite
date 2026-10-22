from mite.stats import Counter, Histogram, extractor, matcher_by_type

_PAGE_LOAD_METRICS = [
    ("dns_lookup_time", "seconds"),
    ("js_onload_time", "seconds"),
    ("page_weight", "seconds"),
    ("render_time", "seconds"),
    ("tcp_time", "seconds"),
    ("tls_time", "seconds"),
    ("time_to_first_byte", "seconds"),
    ("time_to_last_byte", "seconds"),
    ("time_to_interactive", "seconds"),
    ("total_time", "seconds"),
    ("request_start_time", "seconds"),
    ("response_start_time", "seconds"),
    ("response_end_time", "seconds"),
    ("response_size", "bytes"),
    ("status_code", "number"),
]

_NETWORK_RESOURCE_METRICS = [
    ("dns_lookup_time", "seconds"),
    ("tcp_time", "seconds"),
    ("tls_time", "seconds"),
    ("time_to_first_byte", "seconds"),
    ("time_to_last_byte", "seconds"),
    ("total_time", "seconds"),
    ("response_size", "bytes"),
    ("status_code", "number"),
]

_PAINT_METRICS = [("first_contentful_paint", "seconds"), ("first_paint", "seconds")]


_CUSTOM_METRICS = [
    ("execution_time", "seconds"),
]


def build_metrics(metrics, matcher, labels):
    histograms = []
    for metric, unit in metrics:
        bins = [0.0001, 0.001, 0.01, 0.05, 0.1, 0.2, 0.4, 0.8, 1, 2, 4, 8, 16, 32, 64]
        if unit == "bytes":
            bins = [b * 1000 for b in bins]
        elif unit == "number":  # For status codes
            bins = [100, 200, 300, 400, 500, 600]

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
        "mite_playwright_response_total",
        matcher_by_type("playwright_page_load_metrics"),
        extractor("test journey transaction".split()),
    ),
    *build_metrics(_PAGE_LOAD_METRICS, "playwright_page_load", ["transaction"]),
    *build_metrics(
        _NETWORK_RESOURCE_METRICS,
        "playwright_network_resource",
        ["transaction", "resource_path"],
    ),
    *build_metrics(_PAINT_METRICS, "playwright_paint", ["transaction"]),
    *build_metrics(_CUSTOM_METRICS, "playwright", ["transaction"]),
)
