import asyncio
from contextlib import asynccontextmanager

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from mite.exceptions import MiteError


class KafkaError(MiteError):
    pass


class KafkaContext:
    pass


class KafkaProducer:
    def __init__(self, ctx):
        self._loop = asyncio.get_event_loop()
        self._producer = None

    def _remove_producer(self, ctx):
        del ctx.kafka_producer

    async def start(self, *args, **kwargs):
        self._producer = AIOKafkaProducer(*args, **kwargs)
        await self._producer.start()

    async def send_and_wait(self, topic, key=None, value=None, **kwargs):
        await self._producer.send_and_wait(topic, key=key, value=value, **kwargs)

    async def stop(self):
        await self._producer.stop()


class KafkaConsumer:
    def __init__(self, ctx):
        self._loop = asyncio.get_event_loop()
        self._consumer = None
        self._topics = None

    def _remove_consumer(self, ctx):
        del ctx.kafka_consumer

    async def start(self, *args, **kwargs):
        self._consumer = AIOKafkaConsumer(*args, **kwargs)
        self._topics = args

    async def get_messages(self):
        await self._consumer.start()
        async for msg in self._consumer:
            return msg

    async def stop(self):
        await self._consumer.stop()


@asynccontextmanager
async def _kafka_context_manager(ctx):
    ctx.kafka_producer = KafkaProducer(ctx)
    ctx.kafka_consumer = KafkaConsumer(ctx)
    try:
        yield
    except Exception as e:
        print(e)
        raise KafkaError(e)
    finally:
        ctx.kafka_producer._remove_producer(ctx)
        ctx.kafka_consumer._remove_consumer(ctx)


def mite_kafka(func):
    async def wrapper(ctx, *args, **kwargs):
        async with _kafka_context_manager(ctx):
            return await func(ctx, *args, **kwargs)

    return wrapper
