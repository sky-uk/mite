import subprocess
import sys
from unittest.mock import AsyncMock, patch

import pytest
from mocks.mock_context import MockContext

from mite_kafka import KafkaConsumer, KafkaProducer, mite_kafka, mite_kafka_managed_adapter


def test_mite_kafka_no_warning_on_import():
    # subprocess, not importlib.reload: reload() would mutate shared class state
    # in place and corrupt later tests in this process (see mite_http precedent)
    result = subprocess.run(
        [sys.executable, "-W", "error::FutureWarning", "-c", "import mite_kafka"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_mite_kafka_warns_on_use():
    with pytest.warns(FutureWarning, match="mite_kafka will require"):

        @mite_kafka
        async def dummy_journey(ctx):
            pass


def test_mite_kafka_managed_adapter_warns_on_use():
    with pytest.warns(FutureWarning, match="mite_kafka will require"):
        mite_kafka_managed_adapter(bootstrap_servers="localhost:9092")


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
    mock_context = AsyncMock()

    @mite_kafka
    async def dummy_journey(ctx):
        pass

    await dummy_journey(mock_context)

    assert getattr(mock_context, "kafka_producer", None) is None
    assert getattr(mock_context, "kafka_consumer", None) is None


@pytest.mark.asyncio
# FIXME this test fails under tox, passes(?) otherwise
@pytest.mark.xfail(strict=False)
async def test_create_producer():
    # Create a mock for AIOKafkaProducer.start
    producer_start_mock = AsyncMock()
    mock_context = MockContext()

    # Patch AIOKafkaProducer to return the mock
    with patch("aiokafka.AIOKafkaProducer.start", side_effect=producer_start_mock):
        # Create an instance of _KafkaWrapper
        kafka_wrapper = KafkaProducer(mock_context)
        # Call the create_producer method
        await kafka_wrapper.create_and_start(bootstrap_servers="broker_url")
        # Pass the broker URL as a keyword argument
        # Assert that the AIOKafkaProducer class was called with the expected arguments
        producer_start_mock.assert_awaited_once()


@pytest.mark.asyncio
# FIXME this test fails under tox, passes(?) otherwise
@pytest.mark.xfail(strict=False)
async def test_create_consumer():
    # Create a mock for AIOKafkaConsumer.start
    consumer_start_mock = AsyncMock()
    mock_context = MockContext()

    # Patch AIOKafkaConsumer to return the mock

    with patch("aiokafka.AIOKafkaConsumer.start", side_effect=consumer_start_mock):
        # Create an instance of _KafkaWrapper
        kafka_wrapper = KafkaConsumer(mock_context)
        # Call the create_consumer method
        await kafka_wrapper.create_and_start(bootstrap_servers="broker_url")
        # Assert that the AIOKafkaConsumer class was called with the expected arguments
        consumer_start_mock.assert_awaited_once()
