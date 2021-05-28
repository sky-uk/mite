import asyncio
import os
import sys
from random import randint
from unittest.mock import patch

import pytest

from mite_finagle import mite_finagle
from mite_finagle.mux import Dispatch, DispatchStatus, Message
from mite_finagle.thrift import ThriftMessageFactory

old_path = sys.path
sys.path = list(sys.path)
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from foo_service.Foo import Client  # noqa: E402
from foo_service.ttypes import FooRequest  # noqa: E402

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


class ThriftConversation:
    def __init__(self, sock_server):
        self._server = sock_server
        self._seqids = []
        self._requests = []
        self._factories = {}

    def add_exchange(self, factory, req_args, rep_args):
        seqid = randint(1, 1_000_000)
        self._seqids.append(seqid)
        with patch("mite_finagle.thrift._SEQUENCE_NOS", new=iter([seqid])):
            self._server.add_response(
                after=len(
                    Dispatch(
                        seqid, {}, b"", {}, factory.get_request_bytes(*req_args)
                    ).to_bytes()
                ),
                response_bytes=Dispatch.Reply(
                    seqid,
                    DispatchStatus.OK,
                    {},
                    factory.get_reply_bytes(seqid, *rep_args),
                ).to_bytes(),
            )
        print(
            "adding reply",
            Dispatch.Reply(
                seqid,
                DispatchStatus.OK,
                {},
                factory.get_reply_bytes(seqid, *rep_args),
            ).to_bytes(),
        )
        self._requests.append(req_args)
        self._factories[seqid] = factory

    async def serve(self):
        await self._server.serve(5050)

    def play(self):
        for request, seqid in zip(self._requests, self._seqids):
            with patch("mite_finagle.thrift._SEQUENCE_NOS", new=iter([seqid])), patch(
                "mite_finagle._TAGS", new=iter([seqid])
            ):
                yield request

    def received(self):
        r = []
        for m in self._server._received:
            msg = Message.from_bytes(m[4:])
            factory = self._factories[msg.tag]
            r.append(factory.get_request_object(msg.body))
        return r


@pytest.fixture
def thrift_conversation(sock_server):
    return ThriftConversation(sock_server)


@pytest.mark.asyncio
async def test_integration_basic(thrift_conversation):
    factory = ThriftMessageFactory("performfoo", Client)

    thrift_conversation.add_exchange(factory, ("foo",), ("foo",))
    await thrift_conversation.serve()

    @mite_finagle
    async def journey(ctx):
        async with ctx.finagle.connect("127.0.0.1", 5050) as finagle:
            print("connected")
            for req_args in thrift_conversation.play():
                await finagle.send_and_wait(factory, *req_args)

    ctx = MockContext()

    await asyncio.sleep(0)
    await journey(ctx)

    assert thrift_conversation.received() == [FooRequest("foo")]
