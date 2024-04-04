import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from mite_kafka import _KafkaWrapper, mite_kafka
from mocks.mock_context import MockContext
import aiokafka



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
    # Create a mock for AIOKafkaProducer
    producer_mock = AsyncMock()

    # Patch AIOKafkaProducer to return the mock
    with patch('aiokafka.producer.AIOKafkaProducer', new_callable=producer_mock):
        # Create an instance of _KafkaWrapper
        kafka_wrapper = _KafkaWrapper()
        # Call the create_producer method
        await kafka_wrapper.create_producer(bootstrap_servers='broker_url')  # Pass the broker URL as a keyword argument
        # Assert that the AIOKafkaProducer class was called with the expected arguments
        await asyncio.sleep(0)
        producer_mock.assert_called_once_with()

@pytest.mark.asyncio
async def test_create_consumer():
    # Create a mock for AIOKafkaConsumer
    consumer_mock = AsyncMock()

    # Patch AIOKafkaConsumer to return the mock
    with patch('aiokafka.comnsumer.AIOKafkaConsumer', new_callable=consumer_mock):
        # Create an instance of _KafkaWrapper
        kafka_wrapper = _KafkaWrapper()
        # Call the create_consumer method
        await kafka_wrapper.create_consumer(bootstrap_servers='broker_url')  # Pass the broker URL as a keyword argument
        # Assert that the AIOKafkaConsumer class was called with the expected arguments
        await asyncio.sleep(0)
        consumer_mock.assert_called_once_with()
        
