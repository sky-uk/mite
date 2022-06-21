import asyncio
import logging
from contextlib import asynccontextmanager

import aio_pika

from mite.exceptions import MiteError

logger = logging.getLogger(__name__)


class AMQPError(MiteError):
    pass


class _AMQPWrapper:
    def __init__(self):
        self._loop = asyncio.get_event_loop()

    def install(self, context):
        context.amqp = self

    def uninstall(self, context):
        del context.amqp

    async def connect_robust(self, *args, **kwargs):
        kwargs.setdefault("loop", self._loop)
        return await aio_pika.connect_robust(*args, **kwargs)

    async def connect(self, *args, **kwargs):
        kwargs.setdefault("loop", self._loop)
        return await aio_pika.connect(*args, **kwargs)

    def message(self, body, **kwargs):
        if isinstance(body, str):
            body = body.encode("utf-8")
        return aio_pika.Message(body, **kwargs)


@asynccontextmanager
async def _amqp_context_manager(context):
    aw = _AMQPWrapper()
    aw.install(context)
    try:
        yield
    except aio_pika.AMQPException as e:
        raise AMQPError(f"Received an error from AMQP:\n{e.message}") from e
    finally:
        aw.uninstall(context)


def mite_amqp(func):
    async def wrapper(ctx, *args, **kwargs):
        async with _amqp_context_manager(ctx):
            return await func(ctx, *args, **kwargs)

    return wrapper
