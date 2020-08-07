from mite.stats import Counter, Histogram, extractor, matcher_by_type

STATS = (
    Histogram(
        'mite_http_selenium_response_time_seconds',
        matcher_by_type('http_selenium_metrics'),
        extractor=extractor(['transaction'], 'total_time'),
        bins=[0.0001, 0.001, 0.01, 0.05, 0.1, 0.2, 0.4, 0.8, 1, 2, 4, 8, 16, 32, 64],
    ),
    Counter(
        'mite_http_selenium_response_total',
        matcher_by_type('http_selenium_metrics'),
        extractor('test journey transaction'.split()),
    ),
)
