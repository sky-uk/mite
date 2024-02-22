from mite.stats import Accumulator, Extractor, matcher_by_type

# Kafka


def _kafka_extract(msg):
    for key, value in msg["message_name"].items():
        yield (key, msg["topic_name"]), value


_KAFKA_STATS = [
    Accumulator(
        "mite_kafka_producer_stats",
        matcher_by_type("kafka_producer_stats"),
        Extractor(labels=["message_name", "topic_name"], extract=_kafka_extract),
    ),
    Accumulator(
        "mite_kafka_consumer_stats",
        matcher_by_type("kafka_consumer_stats"),
        Extractor(labels=["message_name", "topic_name"], extract=_kafka_extract),
    ),
    Accumulator(
        "mite_kafka_topic_stats",
        matcher_by_type("kafka_topic_stats"),
        Extractor(labels=["message_name", "topic_name"], extract=_kafka_extract),
    ),
]
