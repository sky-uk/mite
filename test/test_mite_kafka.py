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
async def test_create_producer():
    # Mock the AIOKafkaProducer object
    producer_mock = AsyncMock()

    # Patch the AIOKafkaProducer class with the mock
    with patch('mite_kafka.AIOKafkaProducer', return_value=producer_mock) as producer_class_mock:
        # Create an instance of _KafkaWrapper
        kafka_wrapper = _KafkaWrapper()

        # Call the create_producer method
        await kafka_wrapper.create_producer('broker_url')

        # Assert that the AIOKafkaProducer class was called with the expected arguments
        producer_class_mock.assert_called_once_with('broker_url', loop=asyncio.get_event_loop())

        # Assert that the start method of the producer object was awaited once
        producer_mock.start.assert_awaited_once()

        # Assert that the stop method of the producer object was awaited once
        producer_mock.stop.assert_awaited_once()
        
