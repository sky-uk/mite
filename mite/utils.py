import msgpack
import importlib


_msg_unpacker = msgpack.Unpacker(raw=False, use_list=False)


def unpack_msg(msg):
    _msg_unpacker.feed(msg)
    return _msg_unpacker.unpack()


_msg_packer = msgpack.Packer(use_bin_type=True)
pack_msg = _msg_packer.pack


def spec_import(spec):
    module, attr = spec.split(':', 1)
    return getattr(importlib.import_module(module), attr)
