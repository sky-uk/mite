import asyncio
import importlib

import msgpack


def unpack_msg(msg):
    return msgpack.unpackb(msg, use_list=False, raw=False)


def pack_msg(msg):
    return msgpack.packb(msg, use_bin_type=True)


def spec_import(spec):
    module, attr = spec.split(':', 1)
    return getattr(importlib.import_module(module), attr)


async def sleep(delay, always=False, **kwargs):
    await asyncio.sleep(delay, **kwargs)


def _msg_backend_module(opts):
    msg_backend = opts['--message-backend']
    if msg_backend == 'nanomsg':
        from . import nanomsg

        return nanomsg
    elif msg_backend == 'ZMQ':
        from . import zmq

        return zmq
    else:
        raise ValueError('Unsupported backend %r' % (msg_backend,))
