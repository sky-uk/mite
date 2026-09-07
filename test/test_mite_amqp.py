import asyncio
import subprocess
import sys
from unittest.mock import AsyncMock, patch

import aio_pika
import pytest
from mocks.mock_context import MockContext

from mite_amqp import _AMQPWrapper, mite_amqp


def test_mite_amqp_no_warning_on_import():
    # subprocess, not importlib.reload: reload() would mutate shared class state
    # in place and corrupt later tests in this process (see mite_http precedent)
    result = subprocess.run(
        [sys.executable, "-W", "error::FutureWarning", "-c", "import mite_amqp"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_mite_amqp_warns_on_use():
    with pytest.warns(FutureWarning, match="mite_amqp will require"):

        @mite_amqp
        async def dummy_journey(ctx):
            pass


@pytest.mark.asyncio
async def test_mite_amqp_decorator():
    context = MockContext()

    @mite_amqp
    async def dummy_journey(ctx):
        assert ctx.amqp is not None

    await dummy_journey(context)


@pytest.mark.asyncio
async def test_mite_amqp_decorator_uninstall():
    context = MockContext()

    @mite_amqp
    async def dummy_journey(ctx):
        pass

    await dummy_journey(context)

    assert getattr(context, "amqp", None) is None


@pytest.mark.asyncio
async def test_mite_amqp_connect():
    context = MockContext()
    url = "amqp://foo.bar"
    connect_mock = AsyncMock()

    @mite_amqp
    async def dummy_journey(ctx):
        await ctx.amqp.connect(url)

    with patch("aio_pika.connect", side_effect=connect_mock):
        await dummy_journey(context)

    connect_mock.assert_awaited_once_with(url, loop=asyncio.get_running_loop())


@pytest.mark.asyncio
async def test_mite_amqp_connect_robust():
    context = MockContext()
    url = "amqp://foo.bar"

    connect_mock = AsyncMock()

    @mite_amqp
    async def dummy_journey(ctx):
        await ctx.amqp.connect_robust(url)

    with patch("aio_pika.connect_robust", side_effect=connect_mock):
        await dummy_journey(context)

    connect_mock.assert_awaited_once_with(url, loop=asyncio.get_running_loop())


def test_amqp_message():
    w = _AMQPWrapper()
    m = w.message(b"hi")
    assert isinstance(m, aio_pika.Message)


def test_amqp_message_string():
    w = _AMQPWrapper()
    m = w.message("hi")
    assert isinstance(m, aio_pika.Message)
