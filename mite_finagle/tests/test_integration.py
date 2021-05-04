import asyncio
import os
import sys

import pytest
from thrift.protocol.TBinaryProtocol import TBinaryProtocol
from thrift.transport import TTransport
from thrift.Thrift import TMessageType

from mite_finagle import mite_finagle
from mite_finagle.thrift import ThriftMessageFactory
from mite_finagle.mux import Dispatch

old_path = sys.path
sys.path = list(sys.path)
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from foo_service.Foo import Client, performfoo_result  # noqa: E402
from foo_service.ttypes import FooResponse  # noqa: E402

sys.path = old_path


# FIXME
class MockContext:
    def __init__(self):
        self.messages = []
        self.config = {}

    def send(self, message, **kwargs):
        self.messages.append((message, kwargs))

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, value):
        self._config = value

    @property
    def should_stop(self):
        return False

    def transaction(self):
        # TODO
        raise NotImplementedError


@pytest.mark.asyncio
async def test_integration_basic(sock_server):
    factory = ThriftMessageFactory("performfoo", Client)

    trans = TTransport.TMemoryBuffer()
    proto = TBinaryProtocol(trans)
    proto.writeMessageBegin("performfoo", TMessageType.REPLY, 1)
    result = performfoo_result(FooResponse("foo"))
    result.write(proto)
    proto.writeMessageEnd()
    sock_server.add_response(
        after=51,
        response_bytes=Dispatch.Reply(1, 0, {}, trans._buffer.getvalue()).to_bytes(),
    )
    await sock_server.serve(5050)

    @mite_finagle
    async def journey(ctx):
        async with ctx.finagle.connect("127.0.0.1", 5050) as finagle:
            print("connected")
            await finagle.send_and_wait(factory, "foo")

    ctx = MockContext()

    await asyncio.sleep(0)
    await journey(ctx)

    sock_server.assert_received(
        [
            # FIXME: make this less brutal to specify
            b"\x00\x00\x00/\x02\x00\x00\x01\x00\x00\x00\x00\x00\x00\x80\x01\x00"
            + b"\x01\x00\x00\x00\nperformfoo\x00\x00\x00\x01\x0c\x00\x01\x0b\x00"
            + b"\x01\x00\x00\x00\x03foo\x00\x00"
        ]
    )
