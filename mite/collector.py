import json
import logging
import os
import time
from itertools import count

from .utils import unpack_msg

logger = logging.getLogger(__name__)


class Collector:
    def __init__(
        self,
        target_dir=None,
        roll_after=100000,
        collector_id=None,
        filter_fn=None,
        use_json=False,
    ):
        logger.info("Initializing collector")
        if target_dir is None:
            target_dir = "collector_data"
        self._target_dir = os.path.abspath(target_dir)
        self._roll_after = roll_after
        os.makedirs(self._target_dir, exist_ok=True)
        self._collector_id = collector_id
        self._filter_fn = filter_fn
        self._use_json = use_json

        self._current = None
        self._file_counter = count()
        self._rotate_current_file()

    def __del__(self):
        self._current.close()

    @property
    def _current_fn(self):
        return os.path.join(self._target_dir, "current")

    @property
    def _current_st_fn(self):
        return os.path.join(self._target_dir, "current_start_time")

    def process_raw_message(self, raw):
        self._msg_count += 1
        if self._filter_fn is None or self._filter_fn(raw):
            self._write_msg(raw)
        if self._msg_count == self._roll_after:
            self._rotate_current_file()

    def _write_msg(self, msg):
        if self._use_json:
            decoded = unpack_msg(msg)
            self._current.write(json.dumps(decoded).encode() + b"\n")
        else:
            self._current.write(msg)

    def _rotate_current_file(self):
        self._msg_count = 0

        if self._current:
            self._current.close()

        if os.path.isfile(self._current_fn):
            logger.debug("rotating existing current file %s", self._current_fn)
            with open(self._current_st_fn) as f:
                start_time = f.read()
            end_time = int(time.time())
            c = next(self._file_counter)
            fn = os.path.join(
                self._target_dir,
                "_".join(
                    str(x)
                    for x in (
                        start_time,
                        end_time,
                        *([self._collector_id] if self._collector_id else []),
                        c,
                    )
                ),
            )
            logger.info("moving old current %s to %s", self._current_fn, fn)
            os.rename(self._current_fn, fn)

        with open(self._current_st_fn, "w") as f:
            f.write(str(int(time.time())))

        self._current = open(self._current_fn, "wb")
