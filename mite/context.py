import asyncio
import logging
import time
import traceback
import warnings
from itertools import count

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


class _TransactionContextManager:
    def __init__(self, ctx, name):
        self._ctx = ctx
        self._name = name

    async def __aenter__(self):
        await self._ctx._start_transaction(self._name)

    async def __aexit__(self, exception_type, exception_val, traceback):
        try:
            if exception_val and not isinstance(exception_val, (HandledException, KeyboardInterrupt)):
                if isinstance(exception_val, MiteError):
                    await self._ctx._send_mite_error(exception_val, traceback)
                else:
                    await self._ctx._send_exception(exception_val, traceback)
                if self._ctx._debug:
                    drop_to_debugger(traceback)
                if isinstance(exception_val, MiteError):
                    raise HandledMiteError(exception_val, traceback)
                else:
                    raise HandledException(exception_val, traceback)
        finally:
            await self._ctx._end_transaction()


class _ExceptionHandlerContextManager:
    def __init__(self, ctx):
        self._ctx = ctx

    async def __aenter__(self):
        pass

    async def __aexit__(self, exception_type, exception_val, traceback):
        if exception_val:
            if isinstance(exception_val, KeyboardInterrupt):
                return False
            if not isinstance(exception_val, HandledMiteError):
                if not isinstance(exception_val, HandledException):
                    await self._ctx._send_exception(exception_val, traceback)
                    if self._ctx._debug:
                        drop_to_debugger(traceback)
                await asyncio.sleep(1)
            return not self._ctx._debug
        return True


class Context:
    def __init__(self, send, config, id_data=None, should_stop_func=None, debug=False):
        self._send = send
        self._config = config
        if id_data is None:
            id_data = {}
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

    async def send(self, type, **content):
        msg = content
        msg['type'] = type
        self._add_context_headers_and_time(msg)
        await self._send(msg)
        logger.debug("sent message: %s", msg)

    def transaction(self, name):
        return _TransactionContextManager(self, name)

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
        await self.send('exception', message=message, ex_type=ex_type, location=location, stacktrace=stacktrace)

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

    def _exception_handler(self):
        return _ExceptionHandlerContextManager(self)
