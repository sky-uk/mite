import asyncio
from contextlib import asynccontextmanager

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer


class KafkaProducer:
    def __init__(self, ctx):
        self._loop = asyncio.get_event_loop()
        self._producer = None
        self._context = ctx

    async def create_and_start(self, *args, **kwargs):
        self._producer = AIOKafkaProducer(*args, **kwargs)
        await self._producer.start()

    async def send_and_wait(self, topic, key=None, value=None, **kwargs):
        await self._producer.send_and_wait(topic, key=key, value=value, **kwargs)
        self._context.send(
            "kafka_producer_stats",
            topic=topic,
            key=key,
        )

    async def stop(self):
        await self._producer.stop()


class KafkaConsumer:
    def __init__(self, ctx):
        self._loop = asyncio.get_event_loop()
        self._consumer = None
        self._topics = None
        self._context = ctx

    async def create_and_start(self, *topics, **kwargs):
        self._consumer = AIOKafkaConsumer(*topics, **kwargs)
        self._topics = topics
        await self._consumer.start()

    async def get_messages(self):
        async for message in self._consumer:
            self._context.send(
                "kafka_consumer_stats",
                topic=self._topics,
                partition=message.partition,
                offset=message.offset,
            )
            yield message

    async def stop(self):
        await self._consumer.stop()


@asynccontextmanager
async def _kafka_context_manager(ctx):
    ctx.kafka_producer = KafkaProducer(ctx)
    ctx.kafka_consumer = KafkaConsumer(ctx)
    try:
        yield
    finally:
        del ctx.kafka_producer
        del ctx.kafka_consumer


def mite_kafka(func):
    async def wrapper(ctx, *args, **kwargs):
        async with _kafka_context_manager(ctx):
            return await func(ctx, *args, **kwargs)

    return wrapper
