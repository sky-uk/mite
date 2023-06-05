import asyncio
import logging
from contextlib import asynccontextmanager
from functools import wraps

import aio_pika
from aio_pika.abc import AbstractRobustConnection
from aio_pika.pool import Pool

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

    async def connect_robust(self, *args, **kwargs) -> AbstractRobustConnection:
        kwargs.setdefault("loop", self._loop)
        return await aio_pika.connect_robust("amqp://guest:guest@localhost/", **kwargs)
        # return await aio_pika.connect_robust(*args, **kwargs)

    async def connect(self, *args, **kwargs):
        kwargs.setdefault("loop", self._loop)
        return await aio_pika.connect(*args, **kwargs)

    def message(self, body, **kwargs):
        if isinstance(body, str):
            body = body.encode("utf-8")
        return aio_pika.Message(body, **kwargs)


class AMQPSessionWrapper(_AMQPWrapper):
    _session_pools = {}
    channel_pool: Pool
    connection_pool: Pool
    exchange_type = "amq.direct"

    def __init__(self):
        super().__init__()

        # create the initial connection and channel pool
        self.create_connection_pool()
        self.create_channel_pool()

    def create_connection_pool(self) -> Pool:
        # print("creating connection")
        self.connection_pool = Pool(self.connect_robust, max_size=2, loop=self._loop)

    async def channel(self) -> aio_pika.Channel:
        # print("inside channel function")
        async with self.connection_pool.acquire() as connection:
            return await connection.channel()

    def create_channel_pool(self) -> Pool:
        self.channel_pool = Pool(self.channel, max_size=50, loop=self._loop)

    async def publish(self, message) -> None:
        async with self.connection_pool.acquire() as connection:
            channel = await connection.channel()  # Acquire a channel from the acquired connection
            rmq_exchange = await channel.declare_exchange(self.exchange_type, durable=True, passive=True)
            await rmq_exchange.publish(message, routing_key="", timeout=10)

        # async with self.channel_pool.acquire() as channel:  # type: aio_pika.Channel
        #     rmq_exchange = await channel.declare_exchange(self.exchange_type, durable=True, passive=True)
        #     await rmq_exchange.publish(message, routing_key="", timeout=10)

    async def _checkout(self, context):
        return self

    @asynccontextmanager
    async def session_context(self, context):
        context.amqp = await self._checkout(context)
        yield
        # await self._checkin(context.amqp)  # do we need to check in?
        del context.amqp

    @classmethod
    def decorator(cls, func):
        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            loop = asyncio.get_event_loop()
            try:
                instance = cls._session_pools[loop]
            except KeyError:
                instance = cls()
                cls._session_pools[loop] = instance
            async with instance.session_context(ctx):
                return await func(ctx, *args, **kwargs)

        return wrapper


def mite_amqp_s(func):
    return AMQPSessionWrapper.decorator(func)


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
