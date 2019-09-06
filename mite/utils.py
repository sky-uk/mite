import msgpack
import importlib
import asyncio


def unpack_msg(msg):
    return msgpack.unpackb(msg, use_list=False, raw=False)


def pack_msg(msg):
    return msgpack.packb(msg, unse_bin_type=True, strict_types=True)


def spec_import(spec):
    module, attr = spec.split(':', 1)
    return getattr(importlib.import_module(module), attr)


async def sleep(delay, always=False, **kwargs):
    await asyncio.sleep(delay, **kwargs)
