import logging
from contextlib import asynccontextmanager

import websockets
from websockets.exceptions import WebSocketException

from mite.exceptions import MiteError

logger = logging.getLogger(__name__)


class WebsocketError(MiteError):
    pass


class _WebsocketWrapper:
    def __init__(self):
        self.connection = None

    def install(self, context):
        context.websocket = self

    async def uninstall(self, context):
        if self.connection:
            await self.connection.close()
        del context.websocket

    async def connect(self, *args, **kwargs):
        self.connection = await websockets.connect(*args, **kwargs)
        return self.connection

    async def send(self, body, **kwargs):
        await self.connection.send(body)

    async def recv(self):
        return await self.connection.recv()


@asynccontextmanager
async def _websocket_context_manager(context):
    ww = _WebsocketWrapper()
    ww.install(context)
    try:
        yield
    except WebSocketException as e:
        raise WebsocketError(e) from e
    finally:
        await ww.uninstall(context)


def mite_websocket(func):
    async def wrapper(ctx, *args, **kwargs):
        async with _websocket_context_manager(ctx):
            return await func(ctx, *args, **kwargs)

    return wrapper
