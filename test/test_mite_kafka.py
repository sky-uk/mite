import pytest
from unittest.mock import MagicMock
from mite_kafka import _KafkaWrapper, KafkaError, _kafka_context_manager

@pytest.fixture
def kafka_wrapper():
    return _KafkaWrapper()

@pytest.mark.asyncio
async def test_create_producer(kafka_wrapper):
    producer = await kafka_wrapper.create_producer(bootstrap_servers='localhost:9092')
    assert producer is not None

@pytest.mark.asyncio
async def test_create_consumer(kafka_wrapper):
    consumer = await kafka_wrapper.create_consumer(bootstrap_servers='localhost:9092', group_id='test_group')
    assert consumer is not None

@pytest.mark.asyncio
async def test_send_and_wait(kafka_wrapper):
    producer_mock = MagicMock()
    await kafka_wrapper.send_and_wait(producer_mock, 'test_topic', key='test_key', value='test_value')
    producer_mock.start.assert_called_once()
    producer_mock.send_and_wait.assert_called_once_with('test_topic', key='test_key', value='test_value')
    producer_mock.stop.assert_called_once()

@pytest.mark.asyncio
async def test_get_message(kafka_wrapper):
    consumer_mock = MagicMock()
    consumer_mock.__aiter__.return_value = iter([MagicMock()])
    message = await kafka_wrapper.get_message(consumer_mock, 'test_topic')
    assert message is not None
    consumer_mock.start.assert_called_once()
    consumer_mock.stop.assert_called_once()

@pytest.mark.asyncio
async def test_create_message(kafka_wrapper):
    value = 'test_value'
    message = await kafka_wrapper.create_message(value)
    assert message == value

@pytest.mark.asyncio
async def test_kafka_context_manager_success():
    context = MagicMock()
    async with _kafka_context_manager(context):
        pass
    context.kafka.install.assert_called_once()
    context.kafka.uninstall.assert_called_once()

@pytest.mark.asyncio
async def test_kafka_context_manager_exception():
    context = MagicMock()
    with pytest.raises(KafkaError):
        async with _kafka_context_manager(context):
            raise ValueError("Test error")
    context.kafka.install.assert_called_once()
    context.kafka.uninstall.assert_called_once()
