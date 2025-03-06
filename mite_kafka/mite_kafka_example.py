import logging
from functools import wraps

from mite import ensure_fixed_separation
from mite.scenario import StopVolumeModel
from mite_kafka import mite_kafka, mite_kafka_managed_adapter

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kafka broker address
KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"

# Define your Kafka topic
KAFKA_TOPIC = "test_topic3"


def mite_cybertron_kafka_producer_timed_journey(
    separation=1,
    only_producer=True,
    bootstrap_servers=None,
):
    def wrapper_factory(func):
        @wraps(func)
        @mite_kafka_managed_adapter(
            only_producer=only_producer, bootstrap_servers=bootstrap_servers
        )
        async def wrapper(ctx, *args, **kwargs):
            async with ensure_fixed_separation(separation):
                return await func(ctx, *args, **kwargs)

        return wrapper

    return wrapper_factory


def volume_model_factory(n):
    def vm(start, end):
        if start > 60:  # Will run for 15 mins
            raise StopVolumeModel
        return n

    vm.__name__ = f"volume model {n}"
    return vm


# Example function to produce messages to Kafka
@mite_kafka
async def produce_to_kafka(ctx):
    producer = ctx.kafka_producer
    await producer.create_and_start(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)

    message = "Hello Kafka!"

    try:
        await producer.send_and_wait(KAFKA_TOPIC, value=message.encode("utf-8"))
        logger.info(f"Message sent to Kafka: {message} to the topic {KAFKA_TOPIC}")
    finally:
        await producer.stop()


# Example function to produce messages to Kafka
@mite_cybertron_kafka_producer_timed_journey(
    only_producer=True, bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS
)
async def produce_to_kafka_using_managed_adapter(ctx):
    message = "Hello Kafka!"

    await ctx.kafka_producer.send_and_wait(KAFKA_TOPIC, value=message.encode("utf-8"))
    logger.info(f"Message sent to Kafka: {message} to the topic {KAFKA_TOPIC}")


# Example function to consume messages from Kafka
@mite_kafka
async def consume_from_kafka(ctx):
    consumer = ctx.kafka_consumer
    await consumer.create_and_start(
        KAFKA_TOPIC, bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS
    )

    try:
        async for message in consumer.get_messages():
            logger.info(
                f"Received message from Kafka: {KAFKA_TOPIC} - {message.value.decode('utf-8')}"
            )
    finally:
        await consumer.stop()


def scenario():
    return [
        [
            "mite_kafka.mite_kafka_example:produce_to_kafka",
            None,
            volume_model_factory(2),
        ],
        [
            "mite_kafka.mite_kafka_example:consume_from_kafka",
            None,
            volume_model_factory(2),
        ],
    ]


def kafka_managed_adapter_scenario():
    return [
        [
            "mite_kafka.mite_kafka_example:produce_to_kafka_using_managed_adapter",
            None,
            volume_model_factory(2),
        ],
    ]
