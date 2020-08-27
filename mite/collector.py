import time
import os
from itertools import count
import logging


logger = logging.getLogger(__name__)


class Collector:
    def __init__(self, target_dir=None, roll_after_n_messages=100000, collector_id=None):
        logger.info('Starting collector')
        if target_dir is None:
            target_dir = 'collector_data'
        self._target_dir = os.path.abspath(target_dir)
        self._roll_after_n_messages = roll_after_n_messages
        try:
            os.makedirs(self._target_dir)
        except FileExistsError:
            pass
        self._file_counter = count()
        self._current_fn = os.path.join(self._target_dir, 'current')
        self._current_st_fn = os.path.join(self._target_dir, 'current_start_time')
        self._collector_id = collector_id

        self._rotate_current_file()
        self._current = open(self._current_fn, 'wb')
        self._msg_count = 0
        self._tps_start = time.time()
        self._tps_count = 0

    def process_raw_message(self, raw):
        self._msg_count += 1
        self._current.write(raw)
        if self._msg_count == self._roll_after_n_messages:
            self._msg_count = 0
            self._current.close()
            self._rotate_current_file()
            self._current = open(self._current_fn, 'wb')

    def _rotate_current_file(self):
        if os.path.isfile(self._current_fn):
            logger.debug('rotating existing current file %s', self._current_fn)
            with open(self._current_st_fn) as f:
                start_time = f.read()
            end_time = int(time.time())
            c = next(self._file_counter)
            fn = os.path.join(
                self._target_dir,
                '_'.join(str(x) for x in (
                    start_time,
                    end_time,
                    *([self._collector_id] if self._collector_id else []),
                    c
                ))
            )
            logger.warning('moving old current %s to %s', self._current_fn, fn)
            os.rename(self._current_fn, fn)

        with open(self._current_st_fn, 'w') as f:
            f.write(str(int(time.time())))
