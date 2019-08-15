from mite.context import Context
from mocks.mock_sender import SenderMock
from mocks.mock_runner_conf import RunnerConfigMock

test_msg = 'test msg for the unit test'


def test_send():
    config = RunnerConfigMock()
    sender = SenderMock()
    ctx = Context(sender.send, config)

    ctx.send('test_type', message=test_msg, transaction='test')

    assert sender.messages[-1]['message'] == test_msg
    assert sender.messages[-1]['type'] == 'test_type'


def test_start_transaction():
    config = RunnerConfigMock()
    sender = SenderMock()
    ctx = Context(sender.send, config)

    test_transaction_name = "start test transaction for unit test"

    ctx._start_transaction(test_transaction_name)

    assert sender.messages[-1]['type'] == 'start'
    assert test_transaction_name in ctx._transaction_names


def test_end_transaction():
    config = RunnerConfigMock()
    sender = SenderMock()
    ctx = Context(sender.send, config)

    test_transaction_name = "start end transaction for unit test"
    ctx._start_transaction(test_transaction_name)

    ctx._end_transaction()

    assert sender.messages[-1]['type'] == 'end'
    assert test_transaction_name not in ctx._transaction_names
