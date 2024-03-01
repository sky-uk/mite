import asyncio
from unittest.mock import AsyncMock, patch

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import pytest
from mocks.mock_context import MockContext

from mite_kafka import _KafkaWrapper, mite_kafka


@pytest.fixture
def mock_context():
    context = MockContext()
    context.kafka = _KafkaWrapper()  # Assign _KafkaWrapper instance to the kafka attribute
    return context

@pytest.mark.asyncio
async def test_mite_kafka_decorator(mock_context):
    context = mock_context

    @mite_kafka
    async def dummy_journey(ctx):
        assert ctx.kafka is not None

    await dummy_journey(context)

@pytest.mark.asyncio
async def test_mite_kafka_decorator_uninstall(mock_context):
    context = mock_context

    @mite_kafka
    async def dummy_journey(ctx):
        pass

    await dummy_journey(context)

    assert getattr(context, "kafka", None) is None

@pytest.mark.asyncio
async def test_mite_connect_producer(mock_context):
    context = mock_context
    url = "kafka://foo.bar"

    connect_mock = AsyncMock()

    with patch("your_module._KafkaWrapper.create_producer", new=connect_mock):
        await context.kafka.connect_producer(url)

    connect_mock.assert_called_once_with(url, loop=asyncio.get_event_loop())

@pytest.mark.asyncio
async def test_mite_connect_consumer(mock_context):
    context = mock_context
    url = "kafka://foo.bar"

    connect_mock = AsyncMock()

    with patch("your_module._KafkaWrapper.create_consumer", new=connect_mock):
        await context.kafka.connect_consumer(url)

    connect_mock.assert_called_once_with(url, loop=asyncio.get_event_loop())

@pytest.mark.asyncio
async def test_kafka_produce_message(mock_context):
    context = mock_context
    producer = await context.kafka.create_producer()
    m = await context.kafka.send_and_wait(producer, "my_topic", b"hi")
    assert m is not None

@pytest.mark.asyncio
async def test_kafka_consume_message(mock_context):
    context = mock_context
    consumer = await context.kafka.create_consumer()
    m = await context.kafka.get_message(consumer, "my_topic")
    assert m is not None
