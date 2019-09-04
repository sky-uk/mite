import logging
import sys
import time
import traceback
from itertools import count

from contextlib import asynccontextmanager
from .exceptions import MiteError


logger = logging.getLogger(__name__)


def _tb_format_location(tb):
    f_code = tb.tb_frame.f_code
    return f"{f_code.co_filename}:{tb.tb_lineno}:{f_code.co_name}"


class Context:
    def __init__(self, send_fn, config, id_data={}, should_stop_func=None, debug=False):
        self._send_fn = send_fn
        self._config = config
        self._id_data = id_data
        self._should_stop_func = should_stop_func
        self._transaction_names = []
        self._transaction_ids = []
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

    @property
    def _transaction_name(self):
        # Probably badly named, should be current transaction name
        if self._transaction_names:
            return self._transaction_names[-1]
        else:
            return ''

    @property
    def _transaction_id(self):
        # Probably badly named, should be current transaction id
        if self._transaction_ids:
            return self._transaction_ids[-1]
        else:
            return ''

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
        # FIXME: instead of a stack (i.e. list), we can probably use something
        # like a context variable (from py3.7) here.  Alternatively, we might
        # be able to get away with just using local variables (for the old
        # values) and a simple (non-stack) instance var (for the current one)
        self._transaction_ids.append(next(self._trans_id_gen))
        self._transaction_names.append(name)
        start_time = time.time()

        try:
            yield None
        except Exception as e:
            if isinstance(e, MiteError):
                self._send_mite_error(e)
            else:
                self._send_exception(e)
            if self._debug:  # pragma: no cover
                breakpoint()
        finally:
            self.send('txn', start_time=start_time)
            self._transaction_names.pop()
            self._transaction_ids.pop()

    def _send_exception(self, value):
        message = str(value)
        ex_type = type(value).__name__
        tb = sys.exc_info()[2]
        location = _tb_format_location(tb)
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
