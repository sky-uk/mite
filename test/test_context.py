from unittest.mock import Mock

import pytest
from mocks.mock_sender import SenderMock
from pytest import raises

from mite.context import Context
from mite.exceptions import MiteError

test_msg = 'test msg for the unit test'


class MyException(Exception):
    pass


def test_send():
    config = {}
    sender = SenderMock()
    ctx = Context(sender.send, config)

    ctx.send('test_type', message=test_msg, transaction='test')

    assert sender.messages[-1]['message'] == test_msg
    assert sender.messages[-1]['type'] == 'test_type'


@pytest.mark.asyncio
async def test_transaction_start_end():
    send_fn = Mock()
    context = Context(send_fn, {})
    async with context.transaction("foo"):
        pass

    assert send_fn.call_count == 1
    msg = send_fn.call_args[0][0]
    assert msg["type"] == "txn"
    assert "start_time" in msg


@pytest.mark.asyncio
async def test_message_structure():
    send_fn = Mock()
    context = Context(send_fn, {}, id_data={"id": "hello"})
    async with context.transaction("xyz"):
        context.send("foo", bar="quux")
    msg = send_fn.call_args_list[0][0][0]

    assert msg["type"] == "foo"
    assert msg["bar"] == "quux"
    assert msg["id"] == "hello"
    assert msg["transaction"] == "xyz"
    assert msg["transaction_id"] == 1
    assert "time" in msg
    assert len(msg.keys()) == 6


@pytest.mark.asyncio
async def test_nested_transactions():
    send_fn = Mock()
    context = Context(send_fn, {})
    async with context.transaction("outer"):
        async with context.transaction("inner"):
            pass

    assert send_fn.call_count == 2

    inner_end_msg = send_fn.call_args_list[0][0][0]
    assert inner_end_msg["type"] == "txn"
    assert inner_end_msg["transaction"] == "inner"

    outer_end_msg = send_fn.call_args_list[1][0][0]
    assert outer_end_msg["type"] == "txn"
    assert outer_end_msg["transaction"] == "outer"


@pytest.mark.asyncio
async def test_exception():
    send_fn = Mock()
    context = Context(send_fn, {})

    with raises(MyException):
        async with context.transaction("test"):
            raise MyException()

    assert send_fn.call_count == 2

    exn_msg = send_fn.call_args_list[0][0][0]
    assert exn_msg["type"] == "exception"

    end_msg = send_fn.call_args_list[1][0][0]
    assert end_msg["type"] == "txn"


@pytest.mark.asyncio
async def test_exception_not_sent_twice():
    send_fn = Mock()
    context = Context(send_fn, {})

    with raises(MyException):
        async with context.transaction("test"):
            async with context.transaction("inner"):
                raise MyException()

    assert send_fn.call_count == 3  # exception, plus 2 txns

    exn_msg = send_fn.call_args_list[0][0][0]
    assert exn_msg["type"] == "exception"
    assert exn_msg["transaction"] == "inner"


@pytest.mark.asyncio
async def test_mite_error():
    send_fn = Mock()
    context = Context(send_fn, {})

    with raises(MiteError):
        async with context.transaction("test"):
            raise MiteError("foo", bar="quux")

    assert send_fn.call_count == 2

    exn_msg = send_fn.call_args_list[0][0][0]
    assert exn_msg["type"] == "error"
    assert exn_msg["bar"] == "quux"

    end_msg = send_fn.call_args_list[1][0][0]
    assert end_msg["type"] == "txn"
