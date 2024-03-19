import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from mite_kafka import _KafkaWrapper, mite_kafka
from mocks.mock_context import MockContext
from aiokafka.producer import AIOKafkaProducer
from aiokafka import AIOKafkaClient

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
async def test_kafka_producer():
    producer_mock = AsyncMock()
    kafka_wrapper = _KafkaWrapper()
    with patch.object(AIOKafkaClient, "_metadata_update") as mocked:
        async def dummy(*d, **kw):
            return

        mocked.side_effect = dummy
        await kafka_wrapper.create_producer(bootstrap_servers='broker_url')
        await kafka_wrapper.send_and_wait(b"some_topic", b"hello")

        AIOKafkaProducer.assert_called_once_with(
            bootstrap_servers='broker_url',
            loop=asyncio.get_event_loop())
     


        
