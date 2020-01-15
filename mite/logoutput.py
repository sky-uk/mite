import logging
import time


class MsgOutput:
    def __init__(self):
        self._logger = logging.getLogger('MSG')

    def process_message(self, msg):
        stacktrace = msg.pop('stacktrace', None)
        if stacktrace and self._logger.isEnabledFor(logging.WARNING):
            message = msg.pop('message', None)
            ex_type = msg.pop('ex_type', None)
            start = "[%s] %.6f" % (msg.pop('type', None), msg.pop('time', None))
            end = ', '.join("%s=%r" % (k, v) for k, v in sorted(msg.items()))
            self._logger.warning(
                "%s %s\n%s: %s\n%s", start, end, ex_type, message, stacktrace
            )
        elif self._logger.isEnabledFor(logging.DEBUG):
            start = "[%s] %.6f" % (msg.pop('type', None), msg.pop('time', None))
            end = ', '.join("%s=%r" % (k, v) for k, v in sorted(msg.items()))
            self._logger.debug("%s %s", start, end)


class HttpStatsOutput:
    def __init__(self, period=2):
        self._period = period
        self._logger = logging.getLogger('Http Stats')
        self._start_t = None
        self._req_total = 0
        self._req_recent = 0
        self._error_total = 0
        self._error_recent = 0
        self._resp_time_recent = []

    def _pct(self, percentile):
        if not self._resp_time_recent:
            return "None"
        assert 0 <= percentile <= 100
        index = (percentile / 100) * (len(self._resp_time_recent) - 1)
        low_index = int(index)
        offset = index % 1
        if offset == 0:
            return "%.6f" % (self._resp_time_recent[low_index],)
        else:
            a = self._resp_time_recent[low_index]
            b = self._resp_time_recent[low_index + 1]
            interpolated_amount = (b - a) * offset
            return "%.6f" % (a + interpolated_amount,)

    def process_message(self, message):
        if 'type' not in message:
            return
        msg_type = message['type']
        t = time.time()
        if self._start_t is None:
            self._start_t = t
        if self._start_t + self._period < t:
            dt = t - self._start_t
            self._resp_time_recent.sort()
            self._logger.info(
                'Total> #Reqs:%d #Errs:%d', self._req_total, self._error_total
            )
            self._logger.info(
                'Last %d Secs> #Reqs:%d #Errs:%d Req/S:%.1f min:%s 25%%:%s 50%%:%s'
                '75%%:%s 90%%:%s 99%%:%s 99.9%%:%s 99.99%%:%s max:%s',
                self._period,
                self._req_recent,
                self._error_recent,
                self._req_recent / dt,
                self._pct(0),
                self._pct(25),
                self._pct(50),
                self._pct(75),
                self._pct(90),
                self._pct(99),
                self._pct(99.9),
                self._pct(99.99),
                self._pct(100),
            )
            self._start_t = t
            del self._resp_time_recent[:]
            self._req_recent = 0
            self._error_recent = 0
        if msg_type == 'http_metrics':
            self._resp_time_recent.append(message['total_time'])
            self._req_total += 1
            self._req_recent += 1
        elif msg_type == 'http_selenium_metrics':
            self._resp_time_recent.append(message['total_time'])
            self._req_total += 1
            self._req_recent += 1
        elif msg_type in ('error', 'exception'):
            self._error_total += 1
            self._error_recent += 1
