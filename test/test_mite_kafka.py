from unittest.mock import MagicMock, patch

import pytest
from mocks.mock_context import MockContext

from mite_kafka import KafkaConsumer, KafkaProducer, mite_kafka


@pytest.mark.asyncio
async def test_mite_kafka_decorator():
    context = MockContext()

    @mite_kafka
    async def dummy_journey(ctx):
        assert ctx.kafka_producer is not None
        assert ctx.kafka_consumer is not None

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
    producer_mock = MagicMock()
    context = MockContext()

    # Patch AIOKafkaProducer to return the mock
    with patch("aiokafka.producer.AIOKafkaProducer", new_callable=producer_mock):
        # Create an instance of _KafkaWrapper
        kafka_wrapper = KafkaProducer(context)
        # Call the create_producer method
        await kafka_wrapper.create(bootstrap_servers="broker_url")
        # Pass the broker URL as a keyword argument
        # Assert that the AIOKafkaProducer class was called with the expected arguments
        producer_mock.assert_called_once_with()


@pytest.mark.asyncio
async def test_create_consumer():
    # Create a mock for AIOKafkaConsumer
    consumer_mock = MagicMock()
    context = MockContext()

    # Patch AIOKafkaConsumer to return the mock
    with patch("aiokafka.consumer.AIOKafkaConsumer", new_callable=consumer_mock):
        # Create an instance of _KafkaWrapper
        kafka_wrapper = KafkaConsumer(context)
        # Call the create_consumer method
        await kafka_wrapper.create(
            bootstrap_servers="broker_url"
        )  # Pass the broker URL as a keyword argument
        # Assert that the AIOKafkaConsumer class was called with the expected arguments
        consumer_mock.assert_called_once_with()
