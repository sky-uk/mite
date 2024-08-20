from mite.stats import Accumulator,extractor,matcher_by_type

# Kafka

_KAFKA_STATS = [
    Accumulator(
        "mite_kafka_producer_stats",
        matcher_by_type("kafka_producer_stats"),
        extractor(["topic_name"], "total_sent"),
    ),
    Accumulator(
        "mite_kafka_consumer_stats",
        matcher_by_type("kafka_consumer_stats"),
        extractor(["topic_name"], "total_received"),
    ),
]
