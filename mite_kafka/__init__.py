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

    async def connect(self, *args, **kwargs):
        kwargs.setdefault("loop", self._loop)
        return await AIOKafkaProducer(*args, **kwargs)

    async def create_producer(self, *args, **kwargs):
        return await self.connect(*args, **kwargs)

    async def create_consumer(self, *args, **kwargs):
        return await AIOKafkaConsumer(*args, **kwargs)

    def message(self, body, **kwargs):
        if isinstance(body, str):
            body = body.encode("utf-8")
        return {"value": body, **kwargs}


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
