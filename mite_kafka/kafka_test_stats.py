import asyncio
import logging

from mite_kafka import KafkaError, mite_kafka, KafkaContext

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kafka broker address
KAFKA_BOOTSTRAP_SERVERS = 'localhost:9092'

# Define your Kafka topic
KAFKA_TOPIC = 'test_topic1'

# Example function to produce messages to Kafka
@mite_kafka
async def produce_to_kafka(ctx):
    message = "Hello Kafka!"
    producer = await ctx.kafka.create_producer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    try:
        await ctx.kafka.send_and_wait(producer, KAFKA_TOPIC, value=message.encode('utf-8'))
        logger.info(f"Message sent to Kafka: {message}")
        ctx.send("mite_kafka_producer_stats", message=message, topic=KAFKA_TOPIC)
    except KafkaError as e:
        logger.error(f"Error sending message to Kafka: {e}")
    finally:
        await producer.stop()

# Example function to consume messages from Kafka
@mite_kafka
async def consume_from_kafka(ctx):
    consumer = await ctx.kafka.create_consumer(KAFKA_TOPIC, bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS, group_id='test')
    try:
        await consumer.start()
        async for message in consumer:
            logger.info(f"Received message from Kafka: {message.value.decode('utf-8')}")
            ctx.send("mite_kafka_consumer_stats", message=message, topic=KAFKA_TOPIC)
    except KafkaError as e:
        logger.error(f"Error consuming message from Kafka: {e}")
    finally:
        await consumer.stop()

# Example usage of the functions
async def main():
    await produce_to_kafka()

    # Wait for a while before consuming messages
    await asyncio.sleep(2)

    await consume_from_kafka()

if __name__ == "__main__":
    context = KafkaContext()
    asyncio.run(main())