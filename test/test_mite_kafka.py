from unittest.mock import MagicMock, patch

import pytest
from mocks.mock_context import MockContext

from mite_kafka import KafkaConsumer, KafkaProducer, mite_kafka


@pytest.mark.asyncio
async def test_mite_kafka_decorator():
    mock_context = MockContext()

    @mite_kafka
    async def dummy_journey(ctx):
        assert ctx.kafka_producer is not None
        assert ctx.kafka_consumer is not None

    await dummy_journey(mock_context)


@pytest.mark.asyncio
async def test_mite_kafka_decorator_uninstall():
    mock_context = MockContext()

    @mite_kafka
    async def dummy_journey(ctx):
        pass

    await dummy_journey(mock_context)

    assert mock_context.kafka_producer is None
    assert mock_context.kafka_consumer is None


@pytest.mark.asyncio
async def test_create_producer():
    # Create a mock for AIOKafkaProducer
    producer_mock = MagicMock()

    # Patch AIOKafkaProducer to return the mock
    with patch("aiokafka.producer.AIOKafkaProducer", new_callable=lambda: producer_mock):
        # Create an instance of _KafkaWrapper
        kafka_wrapper = KafkaProducer()
        # Call the create_producer method
        await kafka_wrapper.create(bootstrap_servers="broker_url")
        # Pass the broker URL as a keyword argument
        # Assert that the AIOKafkaProducer class was called with the expected arguments
        producer_mock.return_value.assert_called_once_with()


@pytest.mark.asyncio
async def test_create_consumer():
    # Create a mock for AIOKafkaConsumer
    consumer_mock = MagicMock()

    # Patch AIOKafkaConsumer to return the mock
    with patch("aiokafka.consumer.AIOKafkaConsumer", new_callable=lambda: consumer_mock):
        # Create an instance of _KafkaWrapper
        kafka_wrapper = KafkaConsumer()
        # Call the create_consumer method
        await kafka_wrapper.create(bootstrap_servers="broker_url")
        # Assert that the AIOKafkaConsumer class was called with the expected arguments
        consumer_mock.return_value.assert_called_once_with()
