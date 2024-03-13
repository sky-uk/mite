import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from mite_kafka import _KafkaWrapper, mite_kafka
from mocks.mock_context import MockContext

@pytest.mark.asyncio
async def test_mite_kafka_decorator():
    context = MockContext()

    @mite_kafka
    async def dummy_journey(ctx):
        assert ctx.kafka is not None

    await dummy_journey(context)

@pytest.mark.asyncio
async def test_mite_kafka_decorator_uninstall():
    context = MockContext()

    @mite_kafka
    async def dummy_journey(ctx):
        pass

    await dummy_journey(context)

    assert getattr(context, "kafka", None) is None


@pytest.mark.asyncio
async def test_mite_connect_producer():
    context = MockContext()
    url = "kafka://foo.bar"

    connect_mock = AsyncMock()

    @mite_kafka
    async def dummy_journey(ctx):
        await ctx.kafka.create_producer(url)

    with patch("mite_kafka._KafkaWrapper.create_producer", new=connect_mock) as create_producer_mock:
        await dummy_journey(context)

    create_producer_mock.assert_called_once_with(url, loop=asyncio.get_event_loop())


@pytest.mark.asyncio
async def test_mite_connect_consumer():
    context = MockContext()
    url = "kafka://foo.bar"

    connect_mock = AsyncMock()

    @mite_kafka
    async def dummy_journey(ctx):
        await ctx.kafka.create_consumer(url)

    with patch("mite_kafka._KafkaWrapper.create_consumer", new=connect_mock) as create_consumer_mock:
        await dummy_journey(context)

    create_consumer_mock.assert_called_once_with(url, loop=asyncio.get_event_loop())
