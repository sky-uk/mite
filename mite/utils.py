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
        # TODO: tighten to "pip install mite[nanomsg]" once that extra exists.
        # NOTE: fires at first use, not import time, unlike the other
        # integrations' warnings (see mite_http/__init__.py for the general
        # rationale). TODO(packaging): revisit - this one is runtime-
        # conditional on --message-backend, not on package import, and
        # mite/__init__.py imports mite.utils unconditionally, so a
        # module-level warning here would fire in every mite process
        # regardless of backend. Open question for the team.
        warnings.warn(
            "nanomsg support will move to an optional extra in a future mite "
            "3.0 release; no functional change today.",
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
