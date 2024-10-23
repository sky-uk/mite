import asyncio
import logging
from contextlib import asynccontextmanager

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from mite.exceptions import MiteError

logger = logging.getLogger(__name__)


class KafkaError(MiteError):
    pass


class KafkaContext:
    pass


class KafkaProducer:
    def __init__(self):
        self._loop = asyncio.get_event_loop()
        self._producer = None

    def install(self, context):
        context.kafka_producer = self

    def uninstall(self, context):
        del context.kafka_producer

    async def start(self, *args, **kwargs):
        self._producer = AIOKafkaProducer(*args, **kwargs)
        await self._producer.start()

    async def send_and_wait(self, topic, key=None, value=None, **kwargs):
        await self._producer.send_and_wait(topic, key=key, value=value, **kwargs)

    async def stop(self):
        await self._producer.stop()


class KafkaConsumer:
    def __init__(self):
        self._loop = asyncio.get_event_loop()
        self._consumer = None

    def install(self, context):
        context.kafka_consumer = self

    def uninstall(self, context):
        del context.kafka_consumer

    async def start(self, *args, **kwargs):
        self._consumer = AIOKafkaConsumer(*args, **kwargs)
        await self._consumer.start()
        return self._consumer

    async def get_msg(self):
        return self._consumer

    async def get_message(self, consumer, *topics, **kwargs):
        breakpoint()
        async for msg in consumer:
            return msg

    async def stop(self):
        await self._consumer.stop()


@asynccontextmanager
async def _kafka_context_manager(context):
    kp = KafkaProducer()
    kp.install(context)
    kc = KafkaConsumer()
    kc.install(context)
    try:
        yield
    except Exception as e:
        print(e)
        raise KafkaError(e)
    finally:
        kp.uninstall(context)
        kc.uninstall(context)


def mite_kafka(func):
    async def wrapper(ctx, *args, **kwargs):
        async with _kafka_context_manager(ctx):
            ctx.kafka_producer = KafkaProducer()
            ctx.kafka_consumer = KafkaConsumer()
            return await func(ctx, *args, **kwargs)

    return wrapper
