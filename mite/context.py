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
            if isinstance(e, MiteError):
                self._send_mite_error(e)
            else:
                self._send_exception(e)
            if self._debug:  # pragma: no cover
                import ipdb

                ipdb.post_mortem()
                sys.exit(1)
        finally:
            self.send('txn', start_time=start_time, end_time=time.time(), error=error)
            self._transaction_name = old_transaction_name
            self._transaction_id = old_transaction_id

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
