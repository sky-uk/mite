import asyncio
import importlib
import warnings

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
        # TODO(release-B): tighten to "pip install mite[nanomsg]" once that extra
        # exists (see PACKAGING_EXTRAS_PLAN.md step 11).
        # NOTE: fires at first use, not import time — see rationale in mite_http/__init__.py.
        warnings.warn(
            "nanomsg support will move to an optional extra in a future mite 3.0 "
            "release; no functional change today.",
            FutureWarning,
            stacklevel=2,
        )
        from . import nanomsg

        return nanomsg
    elif msg_backend == "ZMQ":
        from . import zmq

        return zmq
    else:
        raise ValueError(f"Unsupported backend {msg_backend}")
