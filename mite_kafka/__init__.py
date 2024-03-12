import asyncio
import logging
from contextlib import asynccontextmanager

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from mite.exceptions import MiteError

logger = logging.getLogger(__name__)

class KafkaError(MiteError):
    pass

class KafkaContext:
    pass

class _KafkaWrapper:
    def __init__(self):
        self._loop = asyncio.get_event_loop()

    def install(self, context):
        context.kafka = self

    def uninstall(self, context):
        del context.kafka

    async def create_producer(self, *args, **kwargs):
        kwargs.setdefault("loop", self._loop)
        return AIOKafkaProducer(*args, **kwargs)

    async def create_consumer(self, *args, **kwargs):
        kwargs.setdefault("loop", self._loop)
        return AIOKafkaConsumer(*args, **kwargs)

    async def send_and_wait(self, producer, topic, key=None, value=None, **kwargs):
        try:
            await producer.start()
            await producer.send_and_wait(topic, key=key, value=value, **kwargs)
        finally:
            await producer.stop()

    async def get_message(self, consumer, *topics, **kwargs):
        try:
            await consumer.start()
            async for msg in consumer:
                return msg
        finally:
            await consumer.stop()

    async def create_message(self, value, **kwargs):
        return value

@asynccontextmanager
async def _kafka_context_manager(context):
    kw = _KafkaWrapper()
    kw.install(context)
    try:
        yield
    except Exception as e:
        raise KafkaError(f"Received an error from Kafka:\n{e}") from e
    finally:
        kw.uninstall(context)

def mite_kafka(func):
    async def wrapper(ctx, *args, **kwargs):
        kafka_wrapper = _KafkaWrapper()
        ctx.kafka = kafka_wrapper  # Assigning _KafkaWrapper instance to ctx.kafka
        try:
            async with _kafka_context_manager(ctx):
                return await func(ctx, *args, **kwargs)
        finally:
            ctx.kafka = None  # Resetting ctx.kafka to None after function execution

    return wrapper
