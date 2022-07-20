import os
import sys
from unittest.mock import patch

from pytest import mark, raises
from thrift.Thrift import TApplicationException

from mite_finagle.thrift import ThriftMessageFactory, _ThriftError

old_path = sys.path
sys.path = list(sys.path)
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from foo_service.Foo import Client  # noqa: E402
from foo_service.ttypes import FooResponse  # noqa: E402

sys.path = old_path


def test_init():
    ThriftMessageFactory("performfoo", Client)


def test_init_with_wrong_client_raises():
    with raises(Exception, match="wrong client passed"):
        ThriftMessageFactory("performfo", Client)


def test_get_bytes():
    f = ThriftMessageFactory("performfoo", Client)
    with patch("mite_finagle.thrift._SEQUENCE_NOS", new=iter([1])):
        assert (
            f.get_request_bytes("bar")
            == b"\x80\x01\x00\x01\x00\x00\x00\nperformfoo\x00\x00\x00\x01\x0c\x00"
            b"\x01\x0b\x00\x01\x00\x00\x00\x03bar\x00\x00"
        )


def test_get_reply():
    f = ThriftMessageFactory("performfoo", Client)
    reply = f.get_reply_object(
        b"\x80\x01\x00\x02\x00\x00\x00\nperformfoo\x00\x00\x00\x01\x0c\x00\x00"
        b"\x0b\x00\x01\x00\x00\x00\x04quux\x00\x00"
    )
    assert isinstance(reply, FooResponse)
    assert reply.responsestring == "quux"
    assert hasattr(reply, "chained_wait")


def test_get_reply_exception():
    f = ThriftMessageFactory("performfoo", Client)
    reply = f.get_reply_object(
        b"\x80\x01\x00\x03\x00\x00\x00\nperformfoo\x00\x00\x00\x01\x0b\x00\x01"
        b"\x00\x00\x00\x06foobar\x08\x00\x02\x00\x00\x04\xd2\x00"
    )
    assert isinstance(reply, _ThriftError)
    assert isinstance(reply._wrapped, TApplicationException)


@mark.asyncio
async def test_chained_wait():
    f = ThriftMessageFactory("performfoo", Client)
    reply = f.get_reply_object(
        b"\x80\x01\x00\x02\x00\x00\x00\nperformfoo\x00\x00\x00\x01\x0c\x00\x00"
        b"\x0b\x00\x01\x00\x00\x00\x04quux\x00\x00"
    )
    reply._sent_time = 0
    with patch("time.time", return_value=0.5), patch("asyncio.sleep") as sleep_mock:
        await reply.chained_wait(1)
    sleep_mock.assert_called_once_with(0.5)


@mark.asyncio
async def test_chained_wait_no_sent_time():
    f = ThriftMessageFactory("performfoo", Client)
    reply = f.get_reply_object(
        b"\x80\x01\x00\x02\x00\x00\x00\nperformfoo\x00\x00\x00\x01\x0c\x00\x00"
        b"\x0b\x00\x01\x00\x00\x00\x04quux\x00\x00"
    )
    with patch("asyncio.sleep") as sleep_mock:
        await reply.chained_wait(1)
    sleep_mock.assert_called_once_with(0.1)


@mark.asyncio
async def test_chained_wait_over_long():
    f = ThriftMessageFactory("performfoo", Client)
    reply = f.get_reply_object(
        b"\x80\x01\x00\x02\x00\x00\x00\nperformfoo\x00\x00\x00\x01\x0c\x00\x00"
        b"\x0b\x00\x01\x00\x00\x00\x04quux\x00\x00"
    )
    reply._sent_time = 0
    with patch("time.time", return_value=2), patch("asyncio.sleep") as sleep_mock:
        await reply.chained_wait(1)
    sleep_mock.assert_not_called()
