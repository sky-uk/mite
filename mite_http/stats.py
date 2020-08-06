import os

from mite.stats import Counter, Histogram, extractor, matcher_by_type


def _generate_stats():
    bins = [
        float(x)
        for x in os.environ.get(
            "MITE_HTTP_HISTOGRAM_BUCKETS",
            "0.0001,0.001,0.01,0.05,0.1,0.2,0.4,0.8,1,2,4,8,16,32,64",
        ).split(",")
    ]

    return (
        Counter(
            name='mite_http_response_total',
            matcher=matcher_by_type('http_metrics'),
            extractor=extractor('test journey transaction method response_code'.split()),
        ),
        Histogram(
            name='mite_http_response_time_seconds',
            matcher=matcher_by_type('http_metrics'),
            extractor=extractor(['transaction'], 'total_time'),
            bins=bins,
        ),
    )


STATS = _generate_stats()


def _generate_dns_stats():
    bins = [
        float(x)
        for x in os.environ.get(
            "MITE_DNS_HISTOGRAM_BUCKETS",
            "0.0001,0.001,0.01,0.05,0.1,0.2,0.4,0.8,1,2,4,8,16,32,64",
        ).split(",")
    ]

    return (
        Histogram(
            name='mite_dns_time',
            matcher=matcher_by_type('http_metrics'),
            extractor=extractor(['transaction'], 'dns_time'),
            bins=bins,
        ),
    )


DNS_STATS = _generate_dns_stats()
