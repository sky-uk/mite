import time


class CollectorMock():
    def __init__(self, target_dir=None, roll_after_n_messages=100000):
        self._msg_count = 0
        self._tps_start = time.time()
        self._tps_count = 0

    def process_raw_message(self, raw):
        self._msg_count += 1
