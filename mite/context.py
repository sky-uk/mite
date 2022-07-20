import importlib
import logging
import os
import sys
import time
import traceback
from contextlib import asynccontextmanager
from contextvars import ContextVar
from itertools import count
from pathlib import PurePath

from .exceptions import MiteError

logger = logging.getLogger(__name__)

active_transaction = ContextVar("active_transaction")

_HERE = PurePath(__file__).parent
_MITE_HTTP = _HERE.parent / "mite_http"
# FIXME: if the mite_http module was installed at mite.http, then we could
# omit this hack, and just use the (single) directory of the mite library for
# the checks.  But that would require a change in the way we package mite,
# which we might or might not ultimately want.  See also:
# https://setuptools.readthedocs.io/en/latest/setuptools.html#declaring-extras-optional-features-with-their-own-dependencies
# Further FIXME: add the other built-in mite modules to the list of paths to
# exclude
_MITE_LIB_PATHS = {str(p) for p in (_HERE, _MITE_HTTP)}


def _tb_format_location(tb):
    try:
        stack_summary = traceback.extract_tb(tb, limit=-1)[0]
        return f"{stack_summary.filename}:{stack_summary.lineno}:{stack_summary.name}"
    except Exception:
        return "unable_to_format_source:0:none"


class Context:
    def __init__(self, send_fn, config, id_data=None, should_stop_func=None, debug=False):
        self._send_fn = send_fn
        self._config = config
        self._id_data = id_data or {}
        self._should_stop_func = should_stop_func
        self._debug = debug
        self._trans_id_gen = count(1)

    @property
    def config(self):
        return self._config

    @property
    def should_stop(self):
        return self._should_stop_func and self._should_stop_func() or False

    @property
    def _active_transaction(self):
        try:
            return active_transaction.get()
        except LookupError:
            return None, None

    def _extend_transaction(self, name):
        current_name, _ = self._active_transaction
        if current_name:
            name = f"{current_name} :: {name}"
        return active_transaction.set((name, next(self._trans_id_gen)))

    def send(self, type, **msg):
        msg = dict(msg)
        msg["type"] = type
        msg["time"] = time.time()
        msg.update(self._id_data)
        txn_name, txn_id = self._active_transaction
        msg["transaction"] = txn_name
        msg["transaction_id"] = txn_id
        self._send_fn(msg)
        logger.debug("sent message: %s", msg)

    @asynccontextmanager
    async def transaction(self, name):
        token = self._extend_transaction(name)
        start_time = time.time()
        error = False
        try:
            yield None
        except Exception as e:
            error = True
            if hasattr(e, "handled"):
                raise

            if isinstance(e, MiteError):
                self._send_exception("error", e, include_fields=True)
            else:
                self._send_exception("exception", e, include_stacktrace=True)
            if self._debug:  # pragma: no cover
                postmortem = os.environ.get("PYTHONPOSTMORTEM", "pdb.post_mortem")
                # Implementation borrowed from PEP 553
                modname, dot, funcname = postmortem.rpartition(".")
                if dot == "":
                    modname = "builtins"
                try:
                    module = importlib.import_module(modname)
                    hook = getattr(module, funcname)
                except Exception:
                    import pdb

                    hook = pdb.post_mortem
                hook()
                sys.exit(1)
            else:
                e.handled = True
                raise
        finally:
            self.send(
                "txn",
                start_time=start_time,
                end_time=time.time(),
                had_error=error,
            )
            active_transaction.reset(token)

    def _send_exception(
        self, metric_name, exn, include_stacktrace=False, include_fields=False
    ):
        message = traceback.format_exception_only(type(exn), exn)[-1].strip()
        ex_type = type(exn).__name__
        tb = sys.exc_info()[2]
        location = _tb_format_location(tb)
        kwargs = {**exn.fields} if include_fields else {}
        if include_stacktrace:
            # FIXME: this winds up sending quite a lot of data on the wire
            # that we don't actually use most of the time... do we want to
            # make it configurable whether to send this?
            stacktrace = "".join(traceback.format_tb(tb))
            kwargs["stacktrace"] = stacktrace
        self.send(
            metric_name,
            message=message,
            ex_type=ex_type,
            location=location,
            **kwargs,
        )
