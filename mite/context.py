import logging
import time
import traceback
import warnings
from itertools import count
import sys

from contextlib import asynccontextmanager
from .exceptions import MiteError


logger = logging.getLogger(__name__)


class HandledException(BaseException):
    def __init__(self, original_exception, original_tb):
        self.original_exception = original_exception
        self.original_tb = original_tb


class HandledMiteError(HandledException):
    pass


def drop_to_debugger(traceback):
    try:
        import ipdb as pdb
    except ImportError:
        warnings.warn('ipdb not available, falling back to pdb')
        import pdb
    pdb.post_mortem(traceback)


class Context:
    def __init__(self, send, config, id_data=None, debug=False):
        self._send_fn = send
        self._config = config
        if id_data is None:
            id_data = {}
        self._id_data = id_data
        self._transaction_names = []
        self._transaction_ids = []
        self._debug = debug
        self._trans_id_gen = count(1)

    @property
    def config(self):
        return self._config

    async def send(self, type, **content):
        msg = content
        msg['type'] = type
        self._add_context_headers_and_time(msg)
        await self._send_fn(msg)
        logger.debug("sent message: %s", msg)

    @asynccontextmanager
    async def transaction(self, name):
        await self._start_transaction(name)
        try:
            yield None
        except:  # noqa: E722
            exception_type, exception_val, traceback = sys.exc_info()
            if isinstance(exception_val, KeyboardInterrupt):
                new_exc = exception_val
            elif isinstance(exception_val, HandledException):
                return
            elif isinstance(exception_val, MiteError):
                await self._send_mite_error(exception_val, traceback)
                new_exc = HandledMiteError(exception_val, traceback)
            else:
                await self._send_exception(exception_val, traceback)
                new_exc = HandledException(exception_val, traceback)

            if self._debug:
                drop_to_debugger(traceback)
                return
            else:
                raise new_exc
        finally:
            await self._end_transaction()

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

    def _add_context_headers(self, msg):
        msg.update(self._id_data)
        msg['transaction'] = self._transaction_name
        msg['transaction_id'] = self._transaction_id

    def _add_context_headers_and_time(self, msg):
        self._add_context_headers(msg)
        msg['time'] = time.time()

    def _extract_filename_lineno_funcname(self, tb):
        f_code = tb.tb_frame.f_code
        return f_code.co_filename, tb.tb_lineno, f_code.co_name

    def _tb_format_location(self, tb):
        return '{}:{}:{}'.format(*self._extract_filename_lineno_funcname(tb))

    async def _send_exception(self, value, tb):
        message = str(value)
        ex_type = type(value).__name__
        location = self._tb_format_location(tb)
        stacktrace = ''.join(traceback.format_tb(tb))
        await self.send(
            'exception',
            message=message,
            ex_type=ex_type,
            location=location,
            stacktrace=stacktrace,
        )

    async def _send_mite_error(self, value, tb):
        location = self._tb_format_location(tb)
        await self.send('error', message=str(value), location=location, **value.fields)

    async def _start_transaction(self, name):
        self._transaction_ids.append(next(self._trans_id_gen))
        self._transaction_names.append(name)
        await self.send('start')

    async def _end_transaction(self):
        await self.send('end')
        self._transaction_names.pop()
        self._transaction_ids.pop()
