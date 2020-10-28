import logging
import sys
import time
import traceback
from contextlib import asynccontextmanager
from itertools import count

from .exceptions import MiteError

logger = logging.getLogger(__name__)


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
        self._transaction_id = None
        self._transaction_name = None
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
        if old_transaction_name is not None:
            self._transaction_name = old_transaction_name + " :: " + name
        else:
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
                self._send_exception("error", e, include_fields=True)
            else:
                self._send_exception("exception", e, include_stacktrace=True)
            if self._debug:  # pragma: no cover
                import ipdb

                ipdb.post_mortem()
                sys.exit(1)
            else:
                e.handled = True
                raise
        finally:
            self.send(
                'txn',
                start_time=start_time,
                end_time=time.time(),
                had_error=error,
            )
            self._transaction_name = old_transaction_name
            self._transaction_id = old_transaction_id

    def _send_exception(
        self, metric_name, exn, include_stacktrace=False, include_fields=False
    ):
        message = traceback.format_exception_only(type(exn), exn)[-1].strip()
        ex_type = type(exn).__name__
        tb = sys.exc_info()[2]
        location = _tb_format_location(tb)
        if include_fields:
            kwargs = {**exn.fields}
        else:
            kwargs = {}
        if include_stacktrace:
            # FIXME: this winds up sending quite a lot of data on the wire
            # that we don't actually use most of the time... do we want to
            # make it configurable whether to send this?
            stacktrace = ''.join(traceback.format_tb(tb))
            kwargs["stacktrace"] = stacktrace
        self.send(
            metric_name,
            message=message,
            ex_type=ex_type,
            location=location,
            **kwargs,
        )
