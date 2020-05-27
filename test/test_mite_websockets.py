from unittest.mock import patch

import pytest
from asyncmock import AsyncMock
from mocks.mock_context import MockContext
from websockets.exceptions import WebSocketException

from mite_websocket import WebsocketError, mite_websocket


@pytest.mark.asyncio
async def test_mite_websocket_decorator():
    context = MockContext()

    @mite_websocket
    async def dummy_journey(ctx):
        assert ctx.websocket is not None

    await dummy_journey(context)


@pytest.mark.asyncio
async def test_mite_websocket_decorator_uninstall():
    context = MockContext()
    connect_mock = AsyncMock()

    @mite_websocket
    async def dummy_journey(ctx):
        await ctx.websocket.connect("wss://foo.bar")

    with patch("websockets.connect", new=connect_mock):
        await dummy_journey(context)

    assert getattr(context, "websocket", None) is None


@pytest.mark.asyncio
async def test_mite_websocket_connect():
    context = MockContext()
    url = "wss://foo.bar"
    connect_mock = AsyncMock()

    @mite_websocket
    async def dummy_journey(ctx):
        await ctx.websocket.connect(url)

    with patch("websockets.connect", new=connect_mock):
        await dummy_journey(context)

    connect_mock.assert_called_once_with(url)


@pytest.mark.asyncio
async def test_mite_websocket_exception_handling():
    context = MockContext()

    @mite_websocket
    async def dummy_journey(ctx):
        raise WebSocketException("Something went wrong")

    with pytest.raises(WebsocketError):
        await dummy_journey(context)
