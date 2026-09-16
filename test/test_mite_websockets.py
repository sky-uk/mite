import subprocess
import sys
from unittest.mock import AsyncMock, patch

import pytest
from mocks.mock_context import MockContext
from websockets.exceptions import WebSocketException

from mite_websocket import WebsocketError, mite_websocket


def test_mite_websocket_no_warning_on_import():
    # subprocess, not importlib.reload: reload() would mutate shared class state
    # in place and corrupt later tests in this process (see mite_http precedent)
    result = subprocess.run(
        [sys.executable, "-W", "error::FutureWarning", "-c", "import mite_websocket"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_mite_websocket_warns_on_use():
    with pytest.warns(FutureWarning, match="mite_websocket will require"):

        @mite_websocket
        async def dummy_journey(ctx):
            pass


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
async def test_mite_websocket_connect_and_send():
    context = MockContext()
    url = "wss://foo.bar"
    msg = "bar"
    connect_mock = AsyncMock()

    @mite_websocket
    async def dummy_journey(ctx):
        return await ctx.websocket.connect(url)

    with patch("websockets.connect", new=connect_mock):
        wb = await dummy_journey(context)
    await wb.send(msg)
    connect_mock.return_value.send.assert_called_once_with(msg)


@pytest.mark.asyncio
async def test_mite_websocket_connect_and_recv():
    context = MockContext()
    url = "wss://foo.bar"
    connect_mock = AsyncMock()

    @mite_websocket
    async def dummy_journey(ctx):
        return await ctx.websocket.connect(url)

    with patch("websockets.connect", new=connect_mock):
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
