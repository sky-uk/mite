from mite.stats import Accumulator, Extractor, extractor, matcher_by_type

# Kafka


def _kafka_extract(msg):
    for key, value in msg["total_received"].items():
        yield (key, msg["topic"]), len(value)


def _websocket_extract(msg):
    for key, value in msg["message"].items():
        yield (key, msg["topic"]), len(value)


_KAFKA_STATS = [
    Accumulator(
        "mite_kafka_tx_stats",
        matcher_by_type("kafka_tx_stats"),
        extractor(["message_name", "write_only", "topic", "event_name"], "total_sent"),
    ),
    Accumulator(
        "mite_kafka_rx_stats",
        matcher_by_type("kafka_rx_stats"),
        Extractor(labels=["message_name", "topic"], extract=_kafka_extract),
    ),
    Accumulator(
        "mite_kafka_external_rx_stats",
        matcher_by_type("kafka_external_rx_stats"),
        Extractor(labels=["message_name", "topic"], extract=_kafka_extract),
    ),
    Accumulator(
        "mite_websocket_recv_stats",
        matcher_by_type("wb_recv_stats"),
        Extractor(labels=["message_name", "topic"], extract=_websocket_extract),
    ),
    Accumulator(
        "mite_websocket_recv_external_stats",
        matcher_by_type("wb_recv_external_stats"),
        Extractor(labels=["message_name", "topic"], extract=_websocket_extract),
    ),
]
