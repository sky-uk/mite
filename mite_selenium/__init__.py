import logging
import time
from contextlib import asynccontextmanager

from selenium.common.exceptions import TimeoutException
from selenium.webdriver import Remote
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from mite.exceptions import MiteError
from mite.utils import spec_import

logger = logging.getLogger(__name__)


class _SeleniumWrapper:
    def __init__(self, context):
        """Constructor pulls capabilities and other webdriver config from the context
        which should allow user to set whatever browser configuration that they want.
        Anything which needs a dictionary or object will be imported from a definition
        using a spec_import'"""
        self._context = context
        # Should only need the capabilities setting, other options for selenium experts
        self._command_executor = self._context.config.get(
            "webdriver_command_executor", "http://127.0.0.1:4444/wd/hub"
        )
        self._keep_alive = self._context.config.get("webdriver_keep_alive", False)
        self._file_detector = self._spec_import_if_none("webdriver_file_detector")
        self._proxy = self._spec_import_if_none("webdriver_proxy")
        self._browser_profile = self._spec_import_if_none("webdriver_browser_profile")
        self._options = self._spec_import_if_none("webdriver_options")

        # Required param
        self._capabilities = self._context.config.get("webdriver_capabilities")
        self._capabilities = spec_import(self._capabilities)

    def _spec_import_if_none(self, config_option):
        value = self._context.config.get(config_option, None)
        if value:
            value = spec_import(value)
        return value

    def _start(self):
        self._context.browser = self
        self._remote = Remote(
            desired_capabilities=self._capabilities,
            command_executor=self._command_executor,
            browser_profile=self._browser_profile,
            proxy=self._proxy,
            keep_alive=self._keep_alive,
            file_detector=self._file_detector,
            options=self._options,
        )
        self._context.raw_webdriver = self._remote

    def _stop(self):
        self._remote.close()

    def _browser_has_timing_capabilities(self):
        return self._remote.capabilities["browserName"] == "chrome"

    def _is_using_tls(self, name):
        return name.startswith("https")

    def _get_tls_timing(self, timings):
        if self._is_using_tls(timings["name"]):
            return timings["connectEnd"] - timings["secureConnectionStart"]
        else:
            logger.info("Secure TLS connection not used, defaulting tls_time to 0")
            return 0

    def _get_tcp_timing(self, timings):
        if self._is_using_tls(timings["name"]):
            return timings["secureConnectionStart"] - timings["connectStart"]
        else:
            return timings["connectEnd"] - timings["connectStart"]

    def _send_page_load_metrics(self):
        if self._browser_has_timing_capabilities():
            performance_entries = self._remote.execute_script(
                "return performance.getEntriesByType('navigation')"
            )

            timings = self._extract_first_entry(performance_entries)
            if timings is None:
                return

            protocol = timings["nextHopProtocol"]
            if protocol != "http/1.1":
                logger.warning(
                    f"Timings may be inaccurate as protocol is not http/1.1: {protocol}"
                )
            metrics = {
                "dns_lookup_time": timings["domainLookupEnd"]
                - timings["domainLookupStart"],
                "dom_interactive": timings["domInteractive"],
                "js_onload_time": timings["domContentLoadedEventEnd"]
                - timings["domContentLoadedEventStart"],
                "page_weight": timings["transferSize"],
                "render_time": timings["domInteractive"] - timings["responseEnd"],
                "tcp_time": self._get_tcp_timing(timings),
                "time_to_first_byte": timings["responseStart"] - timings["connectEnd"],
                "time_to_interactive": timings["domInteractive"]
                - timings["requestStart"],
                "time_to_last_byte": timings["responseEnd"] - timings["connectEnd"],
                "tls_time": self._get_tls_timing(timings),
                "total_time": timings["duration"],
            }
            self._context.send(
                "selenium_page_load_metrics",
                **self._extract_and_convert_metrics_to_seconds(metrics),
            )

    def _extract_first_entry(self, entries):
        if len(entries) != 1:
            logger.error(
                f"Performance entries did not return the expected count: expected 1 - actual {len(entries)}"
            )
            return
        else:
            return entries[0]

    def _extract_and_convert_metrics_to_seconds(self, metrics):
        converted_metrics = dict()
        non_time_based_metrics = ["page_weight", "resource_path"]
        for k, v in metrics.items():
            if k not in non_time_based_metrics:
                converted_metrics[k] = self._convert_ms_to_seconds(v)
            else:
                converted_metrics[k] = v
        return converted_metrics

    def _convert_ms_to_seconds(self, value_ms):
        return value_ms / 1000

    def _retrieve_javascript_metrics(self):
        try:
            return self._remote.execute_script(
                "return performance.getEntriesByType('resource')"
            )
        except Exception:
            logger.error("Failed to retrieve resource performance entries")
            return []

    def _clear_resource_timings(self):
        self._remote.execute_script("performance.clearResourceTimings()")

    def get(self, url):
        self._remote.get(url)
        self._send_page_load_metrics()

    def get_js_metrics_context(self):
        return JsMetricsContext(self)

    def wait_for_element(self, locator, timeout=5):
        try:
            return WebDriverWait(self._remote, timeout).until(
                EC.presence_of_element_located(locator)
            )
        except TimeoutException as te:
            raise MiteError(
                f"Timed out trying to find element '{locator}' in the dom"
            ) from te


class JsMetricsContext:
    def __init__(self, browser):
        self._browser = browser
        self.results = None
        self.start_time = time.time()
        self.execution_time = None

    async def __aenter__(self):
        self._browser._clear_resource_timings()

    async def __aexit__(self, exc_type, exc, tb):
        self.results = self._browser._retrieve_javascript_metrics()
        self.execution_time = time.time() - self.start_time


@asynccontextmanager
async def _selenium_context_manager(context):
    try:
        sw = _SeleniumWrapper(context)
        sw._start()
        yield
    finally:
        sw._stop()


def mite_selenium(func):
    async def wrapper(ctx, *args, **kwargs):
        async with _selenium_context_manager(ctx):
            return await func(ctx, *args, **kwargs)

    return wrapper
