from unittest.mock import patch

import pytest
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
@patch("websockets.connect")
async def test_mite_websocket_decorator_uninstall(connect_mock):
    context = MockContext()

    @mite_websocket
    async def dummy_journey(ctx):
        await ctx.websocket.connect("wss://foo.bar")

    await dummy_journey(context)

    assert getattr(context, "websocket", None) is None


@pytest.mark.asyncio
@patch("websockets.connect")
async def test_mite_websocket_connect(connect_mock):
    context = MockContext()
    url = "wss://foo.bar"

    @mite_websocket
    async def dummy_journey(ctx):
        await ctx.websocket.connect(url)

    await dummy_journey(context)

    connect_mock.assert_called_once_with(url)


@pytest.mark.asyncio
@patch("websockets.connect")
async def test_mite_websocket_connect_and_send(connect_mock):
    context = MockContext()
    url = "wss://foo.bar"
    msg = "bar"

    @mite_websocket
    async def dummy_journey(ctx):
        return await ctx.websocket.connect(url)

    wb = await dummy_journey(context)
    await wb.send(msg)
    connect_mock.return_value.send.assert_called_once_with(msg)


@pytest.mark.asyncio
@patch("websockets.connect")
async def test_mite_websocket_connect_and_recv(connect_mock):
    context = MockContext()
    url = "wss://foo.bar"

    @mite_websocket
    async def dummy_journey(ctx):
        return await ctx.websocket.connect(url)

    wb = await dummy_journey(context)
    await wb.recv()
    connect_mock.return_value.recv.assert_called_once()


@pytest.mark.asyncio
async def test_mite_websocket_exception_handling():
    context = MockContext()

    @mite_websocket
    async def dummy_journey(ctx):
        raise WebSocketException("Something went wrong")

    with pytest.raises(WebsocketError):
        await dummy_journey(context)
