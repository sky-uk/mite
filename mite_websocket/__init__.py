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
        self.connections = []

    def install(self, context):
        context.websocket = self

    async def uninstall(self, context):
        for conn in self.connections:
            if conn:
                await self.close_connection(conn)
        del context.websocket

    async def connect(self, *args, **kwargs):
        conn = await websockets.connect(*args, **kwargs)
        self.connections.append(conn)
        return conn

    def get_connections(self):
        return self.connections

    async def close_connection(self, conn):
        await conn.close()
        self.connections.remove(conn)


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
