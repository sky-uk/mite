import os

from mite.stats import Counter, Extractor, Histogram, extractor, matcher_by_type


def _optional_extractor(labels, value_fn):
    """Like mite.stats.extractor, but skips messages for which value_fn returns None
    (fields that older senders don't include, or that libcurl can't provide)."""

    def extract_items(msg):
        value = value_fn(msg)
        if value is not None:
            yield tuple(msg.get(i, "") for i in labels), value

    extract_items.labels = labels
    return Extractor(labels=labels, extract=extract_items)


def _field(name):
    return lambda msg: msg.get(name)


def _non_zero_field(name):
    # e.g. curl reports connect/TLS times as 0 when a connection is reused; skipping
    # those makes the histogram show the cost of new connections only
    def value(msg):
        v = msg.get(name)
        return v if v else None

    return value


def _http_bins():
    return [
        float(x)
        for x in os.environ.get(
            "MITE_HTTP_HISTOGRAM_BUCKETS",
            "0.0001,0.001,0.01,0.05,0.1,0.2,0.4,0.8,1,2,4,8,16,32,64",
        ).split(",")
    ]


def _size_bins():
    return [
        float(x)
        for x in os.environ.get(
            "MITE_HTTP_SIZE_HISTOGRAM_BUCKETS",
            "128,1024,4096,16384,65536,262144,1048576,4194304,16777216,67108864",
        ).split(",")
    ]


def _generate_stats():
    bins = _http_bins()

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


# (stat name, value function). All are histograms by transaction, in seconds.
_EXTENDED_TIME_HISTOGRAMS = (
    # curl's timings, each measured from the start of the transfer
    ("mite_http_dns_time_seconds", _field("dns_time")),
    ("mite_http_connect_time_seconds", _non_zero_field("connect_time")),
    ("mite_http_tls_time_seconds", _non_zero_field("tls_time")),
    ("mite_http_pretransfer_time_seconds", _field("transfer_start_time")),
    ("mite_http_posttransfer_time_seconds", _field("posttransfer_time")),
    ("mite_http_first_byte_time_seconds", _field("first_byte_time")),
    # measured by httpperf outside curl's timings
    ("mite_http_queue_time_seconds", _field("queue_time")),
    ("mite_http_client_lag_seconds", _field("client_lag")),
)

# (stat name, value function). Histograms by transaction, in bytes.
_EXTENDED_SIZE_HISTOGRAMS = (
    ("mite_http_download_size_bytes", _field("download_size")),
    # Only requests with a body; most requests upload nothing
    ("mite_http_upload_size_bytes", _non_zero_field("upload_size")),
)


def _generate_extended_stats():
    # Opt-in (see DEFAULT_EXCLUDED_PROCESSORS in mite.stats): enable with
    # --stats-extra-processors=mite_http_extended
    return tuple(
        Histogram(
            name=name,
            matcher=matcher_by_type('http_metrics'),
            extractor=_optional_extractor(['transaction'], value),
            bins=bins,
        )
        for histograms, bins in (
            (_EXTENDED_TIME_HISTOGRAMS, _http_bins()),
            (_EXTENDED_SIZE_HISTOGRAMS, _size_bins()),
        )
        for name, value in histograms
    )


EXTENDED_HTTP_STATS = _generate_extended_stats()
