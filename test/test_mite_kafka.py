import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from mocks.mock_context import MockContext

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from mite.exceptions import MiteError
from mite_kafka import mite_kafka, KafkaError, _KafkaWrapper

class MockContext:
    def __init__(self):
        self.kafka = None

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
async def test_mite_kafka_create_producer():
    context = MockContext()
    producer_mock = AsyncMock()

    async def dummy_journey(ctx):
        producer = await ctx.kafka.create_producer("bootstrap_servers")
        assert producer is not None

    with patch.object(_KafkaWrapper, 'create_producer', return_value=producer_mock):
        await dummy_journey(context)
        producer_mock.assert_called_once_with("bootstrap_servers", loop=asyncio.get_event_loop())

@pytest.mark.asyncio
async def test_mite_kafka_create_consumer():
    context = MockContext()
    consumer_mock = AsyncMock()

    async def dummy_journey(ctx):
        consumer = await ctx.kafka.create_consumer("bootstrap_servers", "group_id")
        assert consumer is not None

    with patch.object(_KafkaWrapper, 'create_consumer', return_value=consumer_mock):
        await dummy_journey(context)
        consumer_mock.assert_called_once_with("bootstrap_servers", "group_id", loop=asyncio.get_event_loop())

@pytest.mark.asyncio
async def test_mite_kafka_send_and_wait():
    context = MockContext()
    producer_mock = AsyncMock()

    async def dummy_journey(ctx):
        await ctx.kafka.send_and_wait(producer_mock, "topic")

    with patch.object(_KafkaWrapper, 'send_and_wait') as send_and_wait_mock:
        await dummy_journey(context)
        send_and_wait_mock.assert_called_once_with(producer_mock, "topic", key=None, value=None)

@pytest.mark.asyncio
async def test_mite_kafka_get_message():
    context = MockContext()
    consumer_mock = AsyncMock()

    async def dummy_journey(ctx):
        await ctx.kafka.get_message(consumer_mock, "topic")

    with patch.object(_KafkaWrapper, 'get_message') as get_message_mock:
        await dummy_journey(context)
        get_message_mock.assert_called_once_with(consumer_mock, "topic")

@pytest.mark.asyncio
async def test_mite_kafka_create_message():
    context = MockContext()
    value = "test_value"
    message_mock = AsyncMock()

    async def dummy_journey(ctx):
        message = await ctx.kafka.create_message(value)
        assert message == value

    with patch.object(_KafkaWrapper, 'create_message', return_value=message_mock):
        await dummy_journey(context)
        message_mock.assert_called_once_with(value)

@pytest.mark.asyncio
async def test_mite_kafka_exception():
    context = MockContext()

    @mite_kafka
    async def dummy_journey(ctx):
        raise ValueError("Some error")

    with pytest.raises(KafkaError) as exc_info:
        await dummy_journey(context)

    assert "Received an error from Kafka:\nSome error" == str(exc_info.value)
