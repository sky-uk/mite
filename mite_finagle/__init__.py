import asyncio
import time
from itertools import count

from thrift.protocol.TBinaryProtocol import TBinaryProtocol
from thrift.Thrift import TType, TMessageType
from thrift.transport import TTransport

from .mux import CanTinit, Dispatch, Init, Message, Ping

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


class FinagleMessageFactory:
    def __init__(self, fn_name, args_struct, reply_struct):
        self._fn_name = fn_name
        self._args_struct = args_struct
        self._reply_struct = reply_struct
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
        else:
            # An error was thrown
            raise Exception(f"thrift error occurred: {args}")
        return self._reply_struct(
            **{
                self._reply_struct.thrift_spec[field_id][2]: field_value
                for field_id, field_value in args[0][1]
            }
        )

    # FIXME
    # async def wait(self, seconds):
    #     if (sent_time := getattr(self, "_sent_time")) is None:
    #         raise Exception("message hasn't been sent")
    #     to_sleep = seconds - (time.time() - sent_time)
    #     if to_sleep > 0:
    #         await asyncio.sleep(to_sleep)
    #     else:
    #         # FIXME: log a warning
    #         pass


class MiteFinagle:
    def __init__(self, address, port):
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
        return self

    async def __aexit__(self, exc_type, exc, tb):
        # FIXME: handle errors
        # Do we need to clean up the reader...?
        self._writer.close()
        await self._writer.wait_closed()

    async def replies(self):
        while True:
            done, pending = await asyncio.wait(
                (self._main_loop(), self._replies.get()),
                return_when=asyncio.FIRST_COMPLETED,
            )
            yield done[0].result()

    async def send(self, factory, *args, **kwargs):
        tag = next(self._tags)
        mux_msg = Dispatch(tag, {}, b"", {}, factory.get_bytes(*args, **kwargs))
        self._in_flight[tag] = factory  # FIXME: save a reference to the args?
        await self._send_raw(mux_msg)
        return tag

    async def _send_raw(self, mux_msg):
        print("send_raw", mux_msg.to_bytes())
        self._writer.write(mux_msg.to_bytes())
        await self._writer.drain()

    async def send_and_wait(self, msg_factory, *args, **kwargs):
        tag = await self.send(msg_factory, *args, **kwargs)
        return await self._main_loop(return_msg=tag)

    async def _main_loop(self, return_msg=None, return_after_reply=None):
        while True:
            message = await Message.read_from_async_stream(self._reader)
            print("recv", message.to_bytes())
            if message.type in (Ping.type, Init.type, CanTinit.type):
                await self._send_raw(message.make_reply())
            elif message.type in (Ping.Reply.type, Init.Reply.type, CanTinit.Reply.type):
                if (
                    return_after_reply is not None
                    and return_after_reply.Reply.type == message.type
                ):
                    return
            elif message.type == Dispatch.Reply.type:
                if (factory := self._in_flight.pop(message.tag, None)) is None:
                    raise Exception("unknown reply tag received")
                reply = factory.get_reply(message.body)
                if return_msg is not None and return_msg == message.tag:
                    return reply
                await self._replies.put(reply)
            else:
                breakpoint()
                raise Exception("unknown type")
