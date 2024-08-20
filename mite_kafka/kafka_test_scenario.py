import asyncio
import logging
from mite.scenario import StopVolumeModel
from mite_kafka import KafkaError, mite_kafka

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kafka broker address
KAFKA_BOOTSTRAP_SERVERS = 'localhost:9092'

# Define your Kafka topic
KAFKA_TOPIC = 'test_topic3'

def volume_model_factory(n):
    def vm(start, end):
        if start > 60 :  # Will run for 15 mins
            raise StopVolumeModel
        return n

    vm.__name__ = f"volume model {n}"
    return vm

# Example function to produce messages to Kafka
@mite_kafka
async def produce_to_kafka(ctx):
    sent_ids = 0 
    message = "Hello Kafka!"
    producer = await ctx.kafka.create_producer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    try:
        await ctx.kafka.send_and_wait(producer, KAFKA_TOPIC, value=message.encode('utf-8'))
        logger.info(f"Message sent to Kafka: {message} to the topic {KAFKA_TOPIC}")
        sent_ids +=1
        ctx.send("kafka_producer_stats", message=message, topic_name=KAFKA_TOPIC,total_sent=sent_ids)
    except KafkaError as e:
        logger.error(f"Error sending message to Kafka: {e}")

# Example function to consume messages from Kafka
@mite_kafka
async def consume_from_kafka(ctx):
    receive_ids = 0
    consumer = await ctx.kafka.create_consumer(KAFKA_TOPIC, bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    try:
        async for message in consumer:
            logger.info(f"Received message from Kafka: {message.value.decode('utf-8')}")
            receive_ids += 1
            ctx.send("kafka_consumer_stats", message=message, topic_name=KAFKA_TOPIC, total_received=receive_ids)
    except KafkaError as e:
        logger.error(f"Error consuming message from Kafka: {e}")
    finally:
        await consumer.stop()

        
def scenario():
    return [
        ["mite_kafka.kafka_test_scenario:produce_to_kafka", None, volume_model_factory(2)],
        # ["mite_kafka.kafka_test_stats:consume_from_kafka", None, volume_model_factory(2)]
    ]