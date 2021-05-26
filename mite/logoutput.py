import logging
import math
import time


class MsgOutput:
    def __init__(self):
        self._logger = logging.getLogger("MSG")

    def process_message(self, msg):
        stacktrace = msg.pop("stacktrace", None)
        if stacktrace and self._logger.isEnabledFor(logging.WARNING):
            message = msg.pop("message", None)
            ex_type = msg.pop("ex_type", None)
            start = "[%s] %.6f" % (msg.pop("type", None), msg.pop("time", None))
            end = ", ".join("%s=%r" % (k, v) for k, v in sorted(msg.items()))
            self._logger.warning(
                "%s %s\n%s: %s\n%s", start, end, ex_type, message, stacktrace
            )
        elif self._logger.isEnabledFor(logging.DEBUG):
            start = "[%s] %.6f" % (msg.pop("type", None), msg.pop("time", None))
            end = ", ".join("%s=%r" % (k, v) for k, v in sorted(msg.items()))
            self._logger.debug("%s %s", start, end)


class DebugMessageOutput:
    def __init__(self):
        self._logger = logging.getLogger("Debug Logger")

    def process_message(self, message):
        text = message.get("text")
        if message.get("type") == "debug_console_message" and text:
            self._logger.info(text)


class GenericStatsOutput:
    def __init__(self, period=2):
        self._period = period
        self._logger = logging.getLogger(f"{self.log_name} Stats")
        self._start_t = None
        self._req_total = 0
        self._req_recent = 0
        self._error_total = 0
        self._error_recent = 0
        self._resp_time_recent = []

    def _pct(self, percentile):
        """Percentile calculation with linear interpolation.

        If the samples have an exact split at `percentile`, return that single
        value; otherwise interpolate the nearest two values.

        Requires that `self._resp_time_recent` is sorted.

        """
        if not self._resp_time_recent:
            return "None"
        assert 0 <= percentile <= 100
        index = (percentile / 100) * (len(self._resp_time_recent) - 1)
        fractional_index, index = math.modf(index)
        index = int(index)
        if fractional_index == 0:
            return "%.6f" % (self._resp_time_recent[index],)
        else:
            a = self._resp_time_recent[index]
            b = self._resp_time_recent[index + 1]
            interpolated_amount = (b - a) * fractional_index
            return "%.6f" % (a + interpolated_amount,)

    @property
    def error_total(self):
        return self._error_total

    def print_output(self, t):
        dt = t - self._start_t
        self._resp_time_recent.sort()
        self._logger.info(f"Total> #Reqs:{self._req_total} #Errs:{self._error_total}")
        self._logger.info(
            f"Last {self._period} Secs> #Reqs:{self._req_recent} #Errs:{self._error_recent} "
            + f"Req/S:{self._req_recent / dt:.1f} min:{self._resp_time_recent[0]} "
            + f"25%:{self._pct(25)} 50%:{self._pct(50)} 75%:{self._pct(75)} "
            + f"90%:{self._pct(90)} 99%:{self._pct(99)} 99.9%:{self._pct(99.9)} "
            + f"max:{self._resp_time_recent[-1]}",
        )
        self._start_t = t
        del self._resp_time_recent[:]
        self._req_recent = 0
        self._error_recent = 0

    def process_message(self, message):
        if "type" not in message:
            return
        msg_type = message["type"]
        t = time.time()
        if self._start_t is None:
            self._start_t = t
        if self._start_t + self._period < t:
            self.print_output(t)
        if msg_type in self.message_types:
            self._resp_time_recent.append(message["total_time"])
            self._req_total += 1
            self._req_recent += 1
        elif msg_type in ("error", "exception"):
            self._error_total += 1
            self._error_recent += 1


class HttpStatsOutput(GenericStatsOutput):
    message_types = {
        "http_metrics",
        "http_selenium_page_load_metrics",
        "http_selenium_network_resource_metrics",
    }
    log_name = "Http"


class FinagleStatsOutput(GenericStatsOutput):
    message_types = {"finagle_metrics"}
    log_name = "Finagle"
