import asyncio
from unittest.mock import AsyncMock, patch

import aio_pika
import pytest
from mocks.mock_context import MockContext

from mite_amqp import _AMQPWrapper, mite_amqp


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
# FIXME new for 3.8
# @unittest.mock.patch("aio_pika.connect")
# FIXME this test fails under tox, passes(?) otherwise
@pytest.mark.xfail(strict=False)
async def test_mite_amqp_connect():
    context = MockContext()
    url = "amqp://foo.bar"

    connect_mock = AsyncMock()

    @mite_amqp
    async def dummy_journey(ctx):
        await ctx.amqp.connect(url)

    with patch("aio_pika.connect", new=connect_mock):
        await dummy_journey(context)

    connect_mock.assert_called_once_with(url, loop=asyncio.get_event_loop())


@pytest.mark.asyncio
# FIXME this test fails under tox, passes(?) otherwise
@pytest.mark.xfail(strict=False)
async def test_mite_amqp_connect_robust():
    context = MockContext()
    url = "amqp://foo.bar"

    connect_mock = AsyncMock()

    @mite_amqp
    async def dummy_journey(ctx):
        await ctx.amqp.connect_robust(url)

    with patch("aio_pika.connect_robust", new=connect_mock):
        await dummy_journey(context)

    connect_mock.assert_called_once_with(url, loop=asyncio.get_event_loop())


def test_amqp_message():
    w = _AMQPWrapper()
    m = w.message(b"hi")
    assert isinstance(m, aio_pika.Message)


def test_amqp_message_string():
    w = _AMQPWrapper()
    m = w.message("hi")
    assert isinstance(m, aio_pika.Message)
