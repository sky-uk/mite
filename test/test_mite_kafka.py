import asyncio
from unittest.mock import AsyncMock, patch

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import pytest
from mite_kafka import _KafkaWrapper, mite_kafka

class MockContext:
    pass

@pytest.mark.asyncio
async def test_mite_kafka_decorator():
    context = MockContext()

    @mite_kafka
    async def dummy_journey(ctx):
        assert hasattr(ctx, "kafka")

    await dummy_journey(context)

@pytest.mark.asyncio
async def test_mite_kafka_decorator_uninstall():
    context = MockContext()

    @mite_kafka
    async def dummy_journey(ctx):
        pass

    await dummy_journey(context)

    assert not hasattr(context, "kafka")

@pytest.mark.asyncio
async def test_mite_connect_producer():
    context = MockContext()
    url = "kafka://foo.bar"

    connect_mock = AsyncMock()

    with patch("mite_kafka._KafkaWrapper.create_producer", new=connect_mock) as mock_create_producer:
        await context.kafka.connect_producer(url)

    mock_create_producer.assert_called_once_with(url, loop=asyncio.get_event_loop())


@pytest.mark.asyncio
async def test_mite_connect_consumer():
    context = MockContext()
    url = "kafka://foo.bar"

    connect_mock = AsyncMock()

    with patch("mite_kafka._KafkaWrapper.create_consumer", new=connect_mock) as mock_create_consumer:
        await context.kafka.connect_consumer(url)

    mock_create_consumer.assert_called_once_with(url, loop=asyncio.get_event_loop())

@pytest.mark.asyncio
async def test_kafka_produce_message():
    w = _KafkaWrapper()
    producer = await w.create_producer()
    m = await w.send_and_wait(producer, "my_topic", key=b"key", value=b"hi")
    assert m is not None

@pytest.mark.asyncio
async def test_kafka_consume_message():
    w = _KafkaWrapper()
    consumer = await w.create_consumer()
    m = await w.get_message(consumer, "my_topic")
    assert m is not None

