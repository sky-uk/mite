import asyncio
from unittest.mock import AsyncMock, patch

import aiokafka 
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import pytest
from mocks.mock_context import MockContext

from mite_kafka import _KafkaWrapper, mite_kafka


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
@pytest.mark.xfail(strict=False)
async def test_mite_connect_producer():
    context = MockContext()
    url = "kafka://foo.bar"

    connect_mock = AsyncMock()

    @mite_kafka
    async def dummy_journey(ctx):
        await ctx.kafka.connect_producer(url)

    with patch("aiokafka.connect_producer", new=connect_mock):
        await dummy_journey(context)

    connect_mock.assert_called_once_with(url, loop=asyncio.get_event_loop())

@pytest.mark.asyncio
@pytest.mark.xfail(strict=False)
async def test_mite_connect_consumer():
    context = MockContext()
    url = "kafka://foo.bar"

    connect_mock = AsyncMock()

    @mite_kafka
    async def dummy_journey(ctx):
        await ctx.kafka.connect_consumer(url)

    with patch("aiokafka.connect_consumer", new=connect_mock):
        await dummy_journey(context)

    connect_mock.assert_called_once_with(url, loop=asyncio.get_event_loop())

def test_kafka_produce_message():
    w = _KafkaWrapper()
    m = w.message(b"hi")
    assert isinstance(m, AIOKafkaProducer.send_and_wait("my_topic", m))


def test_kafka_consume_message():
    w = _KafkaWrapper()
    m = w.message(b"hi")
    assert isinstance(m, AIOKafkaConsumer.getone())
