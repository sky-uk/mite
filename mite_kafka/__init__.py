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

    def _uninstall(self, ctx):
        del ctx.kafka_producer

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

    def _uninstall(self, ctx):
        del ctx.kafka_consumer

    async def start(self, *args, **kwargs):
        self._consumer = AIOKafkaConsumer(*args, **kwargs)
        return self._consumer

    async def get_msg(self):
        return self._consumer

    async def get_messages(self):
        await self._consumer.start()
        async for msg in self._consumer:
            return msg

    async def stop(self):
        await self._consumer.stop()


@asynccontextmanager
async def _kafka_context_manager(ctx):
    ctx.kafka_producer = KafkaProducer()
    ctx.kafka_consumer = KafkaConsumer()
    try:
        yield
    except Exception as e:
        print(e)
        raise KafkaError(e)
    finally:
        ctx.kafka_producer._uninstall(ctx)
        ctx.kafka_consumer._uninstall(ctx)


def mite_kafka(func):
    async def wrapper(ctx, *args, **kwargs):
        async with _kafka_context_manager(ctx):
            return await func(ctx, *args, **kwargs)

    return wrapper
