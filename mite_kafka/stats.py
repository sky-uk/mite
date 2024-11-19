from mite.stats import Counter, extractor, matcher_by_type

# Kafka

_KAFKA_STATS = [
    Counter(
        "mite_kafka_producer_stats_counter",
        matcher_by_type("kafka_producer_stats"),
        extractor(["topic", "key"]),
    ),
    Counter(
        "mite_kafka_consumer_stats_counter",
        matcher_by_type("kafka_consumer_stats"),
        extractor(["topic", "partition"]),
    ),
]
