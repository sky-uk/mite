import asyncio
import importlib

import msgpack


def unpack_msg(msg):  # pragma: no cover
    return msgpack.unpackb(msg, use_list=False, raw=False, strict_map_key=False)


def pack_msg(msg):  # pragma: no cover
    return msgpack.packb(msg, use_bin_type=True)


def spec_import(spec):
    module, attr = spec.split(":", 1)
    return getattr(importlib.import_module(module), attr)


async def sleep(delay, always=False, **kwargs):  # pragma: no cover
    await asyncio.sleep(delay, **kwargs)


def _msg_backend_module(opts):
    msg_backend = opts["--message-backend"]
    if msg_backend == "nanomsg":
        from . import nanomsg

        return nanomsg
    elif msg_backend == "ZMQ":
        from . import zmq

        return zmq
    else:
        raise ValueError(f"Unsupported backend {msg_backend}")
