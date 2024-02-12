import asyncio
from unittest.mock import AsyncMock, patch

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import pytest
from mocks.mock_context import MockContext

from mite_kafka import _KafkaWrapper, mite_kafka


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
@pytest.mark.xfail(strict=False)
async def test_mite_kafka_connect():
    context = MockContext()
    url = "kafka://foo.bar"

    connect_mock = AsyncMock()

    @mite_kafka
    async def dummy_journey(ctx):
        await ctx.kafka.connect(url)

    with patch("aiokafka.connect", new=connect_mock):
        await dummy_journey(context)

    connect_mock.assert_called_once_with(url, loop=asyncio.get_event_loop())

@pytest.mark.asyncio
async def test_mite_kafka_consumer(self):
    loop = asyncio.new_event_loop()
    with pytest.deprecated_call():
        consumer = AIOKafkaConsumer(
            self.topic, bootstrap_servers=self.hosts, loop=loop
            )
        loop.run_until_complete(consumer.start())
        try:
            loop.run_until_complete(self.send_messages(0, list(range(0, 10))))
            for _ in range(10):
                loop.run_until_complete(consumer.getone())
        finally:
            loop.run_until_complete(consumer.stop())
            loop.close()


@pytest.mark.asyncio
async def test_mite_kafka_producer(self):
    loop = asyncio.new_event_loop()
    with pytest.deprecated_call():
        producer = AIOKafkaProducer(bootstrap_servers=self.hosts, loop=loop)
        loop.run_until_complete(producer.start())
        try:
            future = loop.run_until_complete(
                producer.send(self.topic, b"Hello, Kafka!", partition=0)
            )
            resp = loop.run_until_complete(future)
            self.assertEqual(resp.topic, self.topic)
            self.assertTrue(resp.partition in (0, 1))
            self.assertEqual(resp.offset, 0)
        finally:
            loop.run_until_complete(producer.stop())
            loop.close()


def test_kafka_message():
    w = _KafkaWrapper()
    m = w.message(b"hi")
    assert isinstance(m, aiokafka.Message)


def test_kafka_message_string():
    w = _KafkaWrapper()
    m = w.message("hi")
    assert isinstance(m, aiokafka.Message)
