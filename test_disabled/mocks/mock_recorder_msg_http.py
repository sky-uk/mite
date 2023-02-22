from .mock_collector import CollectorMock


class RecorderMock():
    def __init__(self, target_dir=None):
        return

    def process_message(self, msg):
        return


class MsgOutputMock():
    def process_message(self, msg):
        msg.pop('stacktrace', None)


class HttpStatsOutputMock():
    def __init__(self, period=2):
        self._period = period
        self._start_t = None
        self._req_total = 0
        self._req_recent = 0
        self._error_total = 0
        self._error_recent = 0
        self._resp_time_recent = []

    def process_message(self, message):
        pass


def setup_mock_msg_processors(receiver):
    msg_output = MsgOutputMock()
    http_stats_output = HttpStatsOutputMock()
    receiver.add_listener(http_stats_output.process_message)
    receiver.add_listener(msg_output.process_message)
    collector = CollectorMock()
    recorder = RecorderMock()
    receiver.add_listener(recorder.process_message)
    receiver.add_raw_listener(collector.process_raw_message)
