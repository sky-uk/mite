import contextlib
import logging
import sys
import time
import traceback
from contextlib import asynccontextmanager
from itertools import count
from pathlib import PurePath

from .exceptions import MiteError

logger = logging.getLogger(__name__)

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
        frame = tb.tb_frame
        while (
            any(frame.f_code.co_filename.startswith(p) for p in _MITE_LIB_PATHS)
            or frame.f_code.co_filename == contextlib.__file__
        ):
            # Keep walking the stack frames until we get to something that's
            # not in mite code, nor in the stdlib's contextlib module (which
            # also shows up in our backtraces).
            frame = frame.f_back
        f_code = frame.f_code
        return f"{f_code.co_filename}:{f_code.co_firstlineno}:{f_code.co_name}"
    except Exception:
        return "unable_to_format_source:0:none"


class Context:
    def __init__(self, send_fn, config, id_data={}, should_stop_func=None, debug=False):
        self._send_fn = send_fn
        self._config = config
        self._id_data = id_data
        self._should_stop_func = should_stop_func
        self._transaction_name = ""
        self._transaction_id = None
        self._debug = debug
        self._trans_id_gen = count(1)

    @property
    def config(self):
        return self._config

    @property
    def should_stop(self):
        if self._should_stop_func is not None:
            return self._should_stop_func()
        return False

    def send(self, type, **msg):
        msg = dict(msg)
        msg['type'] = type
        msg['time'] = time.time()
        msg.update(self._id_data)
        msg['transaction'] = self._transaction_name
        msg['transaction_id'] = self._transaction_id
        self._send_fn(msg)
        logger.debug("sent message: %s", msg)

    @asynccontextmanager
    async def transaction(self, name):
        old_transaction_name = self._transaction_name
        old_transaction_id = self._transaction_id
        self._transaction_id = next(self._trans_id_gen)
        self._transaction_name = name
        start_time = time.time()
        error = False
        try:
            yield None
        except Exception as e:
            error = True
            if hasattr(e, "handled"):
                raise

            if isinstance(e, MiteError):
                self._send_mite_error(e)
            else:
                self._send_exception(e)
            if self._debug:  # pragma: no cover
                import ipdb

                ipdb.post_mortem()
                sys.exit(1)
            else:
                e.handled = True
                raise
        finally:
            self.send('txn', start_time=start_time, end_time=time.time(), had_error=error)
            self._transaction_name = old_transaction_name
            self._transaction_id = old_transaction_id

    def _send_exception(self, value):
        message = str(value)
        ex_type = type(value).__name__
        tb = sys.exc_info()[2]
        location = _tb_format_location(tb)
        # FIXME: this winds up sending quite a lot of data on the wire that we
        # don't actually use most of the time... do we want to make it
        # configurable whether to send this?
        stacktrace = ''.join(traceback.format_tb(tb))
        self.send(
            'exception',
            message=message,
            ex_type=ex_type,
            location=location,
            stacktrace=stacktrace,
        )

    def _send_mite_error(self, value):
        tb = sys.exc_info()[2]
        location = _tb_format_location(tb)
        self.send('error', message=str(value), location=location, **value.fields)
