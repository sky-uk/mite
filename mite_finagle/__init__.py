import asyncio
import time
from contextlib import asynccontextmanager
from functools import wraps
from itertools import count

from thrift.protocol.TBinaryProtocol import TBinaryProtocol
from thrift.Thrift import TMessageType, TType
from thrift.transport import TTransport

from .mux import CanTinit, Dispatch, Init, Message, Ping

# TODO:
# - headers (ptp, request id, ...)
# - figure out how to generate/import cybrtron thrift
# - unit tests and integration tests
# - benchmark
# - backport to the thrift stubs
# - split the thrift stuff into its own file

_SEQUENCE_NOS = count(1)

_READERS = {
    TType.I32: "readI32",
    TType.I64: "readI64",
    TType.STRING: "readString",
}

_SEQ_READERS = {
    TType.LIST: ("readListBegin", "readListEnd"),
    TType.SET: ("readSetBegin", "readSetEnd"),
}


def _read_from_proto(proto):
    # https://github.com/pinterest/thrift-tools/blob/da2c9904d58cbd8cbdd9b21e2acda901cdd4a6ad/thrift_tools/thrift_struct.py#L79
    proto.readStructBegin()
    fields = []
    while True:
        _, ftype, fid = proto.readFieldBegin()
        if ftype == TType.STOP:
            break
        value = _read_of_type(proto, ftype)
        fields.append((fid, value))
    proto.readStructEnd()
    return fields


def _read_of_type(proto, ftype):
    if ftype == TType.STRUCT:
        value = _read_from_proto(proto)
    elif ftype in (TType.LIST, TType.SET):
        # Don't distinguish between sequence types, for now
        start, end = _SEQ_READERS[ftype]
        elem_type, nelem = getattr(proto, start)()
        value = [_read_of_type(proto, elem_type) for _ in range(nelem)]
        getattr(proto, end)()
    elif ftype in _READERS:
        value = getattr(proto, _READERS[ftype])()
    elif ftype == TType.MAP:
        ktype, vtype, size = proto.readMapBegin()
        value = {
            _read_of_type(proto, ktype): _read_of_type(proto, vtype) for _ in range(size)
        }
        proto.readMapEnd()
    else:
        raise Exception(f"unknown ftype: {ftype}")

    return value


def write_struct(proto, name, fields):
    proto.writeStructBegin(name)
    for name, type, id, value in fields:
        proto.writeFieldBegin(name, type, id)
        value.write(proto)
        proto.writeFieldEnd()
    proto.writeFieldStop()
    proto.writeStructEnd()


async def _result_wait(self, seconds):
    # Slightly weird -- a function with a `self` argument outside of a class.
    # This is not for calling directly; rather we will add it as an attribute
    # to the class representing the Thrift call result (which is generated
    # from thrift code, so we can't add the method in a "normal" way)
    if (sent_time := getattr(self, "_sent_time")) is None:
        print("sent_time not found")
        # This means we're in a weird racy universe.  We don't want to not
        # sleep at all, as that seems likely to make the races worse.  So
        # we'll do a small wait to try to stabilize.
        to_sleep = 0.1
    else:
        # Remember kids: python has function scope
        to_sleep = seconds - (time.time() - sent_time)
    if to_sleep > 0:
        await asyncio.sleep(to_sleep)
    else:
        # FIXME: log a warning
        pass


class _FinagleError:
    def __init__(self, wrapped):
        self._wrapped = wrapped


class FinagleMessageFactory:
    def __init__(self, fn_name, args_struct, reply_struct, stats_name=None):
        self._fn_name = fn_name
        self._args_struct = args_struct
        self._reply_struct = reply_struct
        self._stats_name = stats_name or fn_name
        self._reply_struct.chained_wait = _result_wait
        self._seq_no = next(_SEQUENCE_NOS)

    def get_bytes(self, *args, **kwargs):
        out_msg = self._args_struct(*args, **kwargs)
        seq_no = next(_SEQUENCE_NOS)
        trans = TTransport.TMemoryBuffer()
        proto = TBinaryProtocol(trans)
        proto.writeMessageBegin(self._fn_name, TMessageType.CALL, seq_no)
        write_struct(proto, "_args", (("_request", TType.STRUCT, 1, out_msg),))
        proto.writeMessageEnd()
        return trans._buffer.getvalue()

    def get_reply(self, msg):
        trans = TTransport.TMemoryBuffer(msg)
        proto = TBinaryProtocol(trans)
        method, mtype, seqid = proto.readMessageBegin()
        args = _read_from_proto(proto)
        proto.readMessageEnd()
        if args[0][0] == 0:
            # Success; the reply is the value of the 0th field
            args = args[0][1]
            result = self._reply_struct(
                **{
                    self._reply_struct.thrift_spec[field_id][2]: field_value
                    for field_id, field_value in args
                }
            )
        else:
            # An error was thrown
            print("finagle error")
            result = _FinagleError(args)
        return result


class MiteFinagleError(Exception):
    pass


class MiteFinagleConnection:
    def __init__(self, context, address, port):
        self._context = context
        self._address = address
        self._port = port
        self._replies = asyncio.Queue()
        self._tags = count(1)
        # FIXME: some sort of length limit to keep this from leaking...?
        self._in_flight = {}

    async def __aenter__(self):
        self._reader, self._writer = await asyncio.open_connection(
            self._address, self._port
        )
        # await self._send_raw(CanTinit(next(self._tags), b"tinit check"))
        # await self._main_loop(return_after_reply=CanTinit)
        # await self._send_raw(Init(next(self._tags), 1))
        # await self._main_loop(return_after_reply=Init)
        return  # FIXME: to get the folding right

    async def __aexit__(self, exc_type, exc, tb):
        # FIXME: handle errors
        # Do we need to clean up the reader...?
        self._writer.close()
        await self._writer.wait_closed()

    async def replies(self):
        pending = (self._main_loop(), self._replies.get())
        while True:
            done, pending = await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for x in done:
                yield self._process_result(x.result())
            pending = (self._replies.get(), *pending)

    async def send(self, factory, *args, **kwargs):
        tag = next(self._tags)
        mux_msg = Dispatch(tag, {}, b"", {}, factory.get_bytes(*args, **kwargs))
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
        # that's nto the same as impossible.)  So we need to have a two-step
        # procedure: save the reference to the outgoing message's factory
        # before sending it, then save the time it was sent afterwards.
        self._in_flight[tag] = [factory, None]
        sent_time = await self._send_raw(mux_msg)
        self._in_flight[tag][1] = sent_time
        return tag

    async def _send_raw(self, mux_msg):
        # print("send_raw", mux_msg.to_bytes())
        self._writer.write(mux_msg.to_bytes())
        sent_time = time.time()
        await self._writer.drain()
        return sent_time

    async def send_and_wait(self, msg_factory, *args, **kwargs):
        tag = await self.send(msg_factory, *args, **kwargs)
        result = await self._main_loop(return_msg=tag)
        return self._process_result(result)

    async def _main_loop(self, return_msg=None, return_after_reply=None):
        while True:
            message = await Message.read_from_async_stream(self._reader)
            # print("recv", message.to_bytes())
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
                    raise Exception("unknown reply tag received")
                factory, sent_time = data
                reply = factory.get_reply(message.body)
                reply._sent_time = sent_time
                self._send_stat(
                    name=factory._stats_name,
                    sent_time=sent_time,
                    had_error=isinstance(reply, _FinagleError),
                )
                if return_msg is not None and return_msg == message.tag:
                    return reply
                await self._replies.put(reply)
            else:
                breakpoint()
                raise Exception("unknown type")

    def _send_stat(self, name, sent_time, had_error):
        self.context.send(
            "finagle_metrics",
            start_time=sent_time,
            total_time=time.time() - sent_time,
            function=name,
            had_error=had_error,
        )

    def _process_result(self, result):
        if isinstance(result, _FinagleError):
            raise MiteFinagleError("encountered thrift error", _FinagleError._wrapped)
        else:
            return result


class MiteFinagle:
    def __init__(self, context):
        self._context = context

    @asynccontextmanager
    async def connect(self, address, port):
        conn = MiteFinagleConnection(self, address, port)
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
