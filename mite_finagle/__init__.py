import asyncio
import time
from contextlib import asynccontextmanager
from functools import wraps
from itertools import count

try:
    from .mux import CanTinit, Dispatch, Init, Message, Ping
    from .thrift import _ThriftError
except ImportError as e:
    # FIXME: are we sure this is the only kind of ImportError we will get?
    raise ModuleNotFoundError(
        "The mite_finagle module requires the thrift package to be installed"
    ) from e

# TODO:
# - headers (ptp, request id, ...)
# - figure out how to generate/import cybertron thrift
# - unit tests and integration tests
# - benchmark
# - backport to the thrift stubs
# - split the thrift stuff into its own file
# - stats hooks for journey test output

_TAGS = count(1)


class MiteFinagleError(Exception):
    pass


class MiteFinagleConnection:
    def __init__(self, context, address, port):
        self._context = context
        self._address = address
        self._port = port
        self._replies = asyncio.Queue()
        # FIXME: some sort of length limit to keep this from leaking...?
        self._in_flight = {}
        self._pending = ()

    async def __aenter__(self):
        self._reader, self._writer = await asyncio.open_connection(
            self._address, self._port
        )

    async def __aexit__(self, exc_type, exc, tb):
        # FIXME: handle errors
        # Do we need to clean up the reader...?
        for task in self._pending:
            task.cancel()
        self._writer.close()
        await self._writer.wait_closed()

    async def replies(self):
        self._pending = (self._main_loop(), self._replies.get())
        while True:
            done, self._pending = await asyncio.wait(
                self._pending,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for x in done:
                yield self._process_result(x.result())
            self._pending = (self._replies.get(), *self._pending)

    async def send(self, factory, *args, mux_context={}, **kwargs):
        tag = next(_TAGS)
        mux_msg = Dispatch(
            tag, mux_context, b"", {}, factory.get_request_bytes(*args, **kwargs)
        )
        # A bit of an awkward dance.  We want to save the time the message was
        # sent, so that the chained_wait function can work.  We can't just
        # store the current time on the next line, though, because we are
        # awaiting the send function, so other coroutines might run before we
        # get around to doing the send.  Similarly, I am not totally sure we
        # can defer setting the self._in_flight until after the send function
        # returns.  I think it's possible, under the right (wrong) combination
        # of async events, for the message reply to be processed by _main_loop
        # before control returns from the await.  (The timings of network
        # roundtrips on a remote connection make it vanishingly unlikely, but
        # that's not the same as impossible.)  So we need to have a two-step
        # procedure: save the reference to the outgoing message's factory
        # before sending it, then save the time it was sent afterwards.
        self._in_flight[tag] = [factory, None]
        print(time.time(), "send", tag)
        sent_time = await self._send_raw(mux_msg)
        print(time.time(), "sent", tag)
        self._in_flight[tag][1] = sent_time
        return tag

    async def _send_raw(self, mux_msg):
        # print("send_raw", mux_msg.to_bytes())
        self._writer.write(mux_msg.to_bytes())
        sent_time = time.time()
        await self._writer.drain()
        return sent_time

    async def send_and_wait(self, msg_factory, *args, mux_context={}, **kwargs):
        tag = await self.send(msg_factory, *args, mux_context=mux_context, **kwargs)
        result = await self._main_loop(return_msg=tag)
        return self._process_result(result)

    async def _main_loop(self, return_msg=None, return_after_reply=None):
        while True:
            message = await Message.read_from_async_stream(self._reader)
            # print("recv", message.to_bytes())
            print(time.time(), "read", message.tag, self._replies.qsize())
            if message.type in (Ping.type, Init.type, CanTinit.type):
                await self._send_raw(message.make_reply())
            elif message.type in (Ping.Reply.type, Init.Reply.type, CanTinit.Reply.type):
                if (
                    return_after_reply is not None
                    and return_after_reply.Reply.type == message.type
                ):
                    return
            elif message.type == Dispatch.Reply.type:
                if (data := self._in_flight.pop(message.tag, None)) is None:
                    raise ValueError("unknown reply tag received")
                factory, sent_time = data
                reply = factory.get_reply_object(message.body)
                reply._sent_time = sent_time
                self._send_stat(
                    name=factory._stats_name,
                    sent_time=sent_time,
                    had_error=isinstance(reply, _ThriftError),
                )
                if return_msg is not None and return_msg == message.tag:
                    return reply
                self._replies.put_nowait(reply)
            else:
                breakpoint()
                raise ValueError("unknown type")

    def _send_stat(self, name, sent_time, had_error):
        self._context.send(
            "finagle_metrics",
            start_time=sent_time,
            total_time=time.time() - sent_time,
            function=name,
            had_error=had_error,
        )

    def _process_result(self, result):
        if isinstance(result, _ThriftError):
            raise MiteFinagleError("encountered thrift error", result._wrapped)
        else:
            return result


class MiteFinagle:
    def __init__(self, context):
        self._context = context

    @asynccontextmanager
    async def connect(self, address, port):
        conn = MiteFinagleConnection(self._context, address, port)
        async with conn:
            yield conn


def mite_finagle(f):
    @wraps(f)
    async def inner(ctx, *args, **kwargs):
        if getattr(ctx, "finagle", None) is not None:
            raise Exception("Context has had mite_finagle applied twice -- this is a bug")
        ctx.finagle = MiteFinagle(ctx)
        result = await f(ctx, *args, **kwargs)
        del ctx.finagle
        return result

    return inner
