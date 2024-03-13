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
    # Create a mock instance of AIOKafkaProducer
    producer_mock = AsyncMock()
    
    # Patch the AIOKafkaProducer with the mock
    with patch('mite_kafka.AIOKafkaProducer', return_value=producer_mock) as mock_kafka_producer:
        # Create an instance of _KafkaWrapper
        kafka_wrapper = _KafkaWrapper()
        
        # Call the create_producer method
        await kafka_wrapper.create_producer('bootstrap_servers', client_id='test_client')

        # Assert that AIOKafkaProducer is called with the correct arguments
        mock_kafka_producer.assert_called_once_with('bootstrap_servers', loop=asyncio.get_event_loop(), client_id='test_client')

        # Assert that the producer is started
        producer_mock.start.assert_awaited_once()

        # Assert that the producer is stopped
        producer_mock.stop.assert_awaited_once()