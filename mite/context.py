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
        data = {"start_time": time.time(), "error": False}

        try:
            yield None
        except Exception as e:
            data["error"] = True
            tb = sys.exc_info()[2]
            if isinstance(e, MiteError):
                data.update(
                    {
                        "message": str(e),
                        # FIXME: always gets the location of "try: yield None"
                        # above; may need to go down the stack frame a bit
                        "location": _tb_format_location(tb),
                        "stacktrace": traceback.format_tb(tb),
                        **e.fields,
                    }
                )
                self._send_mite_error(e)
            else:
                data.update(
                    {
                        "message": str(e),
                        "ex_type": type(e).__name__,
                        # FIXME: see above
                        "location": _tb_format_location(tb),
                        "stacktrace": traceback.format_tb(tb),
                    }
                )
                self._send_exception(e)
            if self._debug:  # pragma: no cover
                import ipdb

                ipdb.post_mortem()
                sys.exit(1)
        finally:
            data["end_time"] = time.time()
            data["total_time"] = data["end_time"] - data["start_time"]
            self.send('txn', **data)
            self._transaction_name = old_transaction_name
            self._transaction_id = old_transaction_id
