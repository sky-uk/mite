import logging
import asyncio
import aio-pika

from contextlib import asynccontextmanager
from mite.utils import spec_import

logger = logging.getLogger(__name__)


class _AMQPWrapper:
    def __init__(self, context):
        self._loop = asyncio.get_event_loop()
        context.amqp = self

    async def connect_robust(self, *args, **kwargs):
        if 'loop' not in kwargs:
            kwargs['loop'] = self._loop
        return await aio_pika.connect_robust(*args, **kwargs)

    async def connect(self):
        if 'loop' not in kwargs:
            kwargs['loop'] = self._loop
        return await aio_pika.connect(*args, **kwargs)


@asynccontextmanager
async def _amqp_context_manager(context):
    aw = _AMQPWrapper(context)
    yield


def mite_amqp(func):
    async def wrapper(ctx, *args, **kwargs):
        async with _amqp_context_manager(ctx):
            return await func(ctx, *args, **kwargs)
    return wrapper
