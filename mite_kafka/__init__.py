import asyncio
import logging
from contextlib import asynccontextmanager

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from mite.exceptions import MiteError

logger = logging.getLogger(__name__)


class KafkaError(MiteError):
    pass


class _KafkaWrapper:
    def __init__(self):
        self._loop = asyncio.get_event_loop()

    def install(self, context):
        context.kafka = self

    def uninstall(self, context):
        del context.kafka

    async def create_producer(self, *args, **kwargs):
        return AIOKafkaProducer(*args, loop=self._loop, **kwargs)

    async def create_consumer(self, *args, **kwargs):
        return AIOKafkaConsumer(*args, loop=self._loop, **kwargs)

    async def start_producer(self, producer):
        await producer.start()

    async def stop_producer(self, producer):
        await producer.stop()

    async def start_consumer(self, consumer):
        await consumer.start()

    async def stop_consumer(self, consumer):
        await consumer.stop()

    async def send_message(self, producer, topic, message):
        await producer.send(topic, message)

    async def receive_messages(self, consumer, topic):
        async for message in consumer:
            yield message


@asynccontextmanager
async def _kafka_context_manager(context):
    kw = _KafkaWrapper()
    kw.install(context)
    try:
        yield
    except Exception as e:
        raise KafkaError(f"Received an error from Kafka:\n{str(e)}") from e
    finally:
        kw.uninstall(context)


def mite_kafka(func):
    async def wrapper(ctx, *args, **kwargs):
        async with _kafka_context_manager(ctx):
            return await func(ctx, *args, **kwargs)

    return wrapper
