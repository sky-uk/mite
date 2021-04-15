import asyncio
import time
from dataclasses import dataclass
from importlib import import_module
from itertools import count
from typing import Any

from thrift.protocol.TBinaryProtocol import TBinaryProtocol
from thrift.transport import TTransport

_SEQUENCE_NOS = count(1)


async def _result_wait(self, seconds):
    # Slightly weird -- a function with a `self` argument outside of a class.
    # This is not for calling directly; rather we will add it as an attribute
    # to the class representing the Thrift call result (which is generated
    # from thrift code, so we can't add the method in a "normal" way)
    if (sent_time := getattr(self, "_sent_time", None)) is None:
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


@dataclass
class _ReadProxy:
    _iprot: Any


@dataclass
class _WriteProxy:
    _seqid: int
    _oprot: Any


class FinagleMessageFactory:
    def __init__(self, fn_name, client, stats_name=None):
        self._fn_name = fn_name
        self._client = client
        self._stats_name = stats_name or fn_name
        if getattr(client, fn_name, None) is None:
            raise Exception(f"wrong client passed when instantiating message factory for: {fn_name}")
        # Monkeypatch the chained_wait method onto the reply class
        module = import_module(client.__module__)
        reply_class = getattr(module, fn_name + "_result").thrift_spec[0][3][0]
        reply_class.chained_wait = _result_wait
        self._args_struct = getattr(module, fn_name + "_args").thrift_spec[1][3][0]

    def get_bytes(self, *args, **kwargs):
        out_msg = self._args_struct(*args, **kwargs)
        seq_no = next(_SEQUENCE_NOS)
        trans = TTransport.TMemoryBuffer()
        proto = TBinaryProtocol(trans)
        proxy = _WriteProxy(seq_no, proto)
        getattr(self._client, "send_" + self._fn_name)(proxy, out_msg)
        return trans._buffer.getvalue()

    def get_reply(self, msg):
        trans = TTransport.TMemoryBuffer(msg)
        proto = TBinaryProtocol(trans)
        proxy = _ReadProxy(proto)
        try:
            result = getattr(self._client, "recv_" + self._fn_name)(proxy)
        except Exception as e:
            print("finagle error", str(e))
            result = _FinagleError(e)
        return result
