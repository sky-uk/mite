import importlib.util
import logging
import socket
import time
from contextlib import asynccontextmanager
from copy import deepcopy
from functools import wraps

from selenium.common.exceptions import TimeoutException
from selenium.webdriver import Remote as SeleniumRemote
from selenium.webdriver.remote.remote_connection import RemoteConnection
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
        self._command_executor = RemoteConnection(
            self._context.config.get(
                "webdriver_command_executor", "http://127.0.0.1:4444/wd/hub"
            ),
            resolve_ip=False,
        )
        self._keep_alive = self._context.config.get("webdriver_keep_alive", False)
        self._file_detector = self._spec_import_if_not_none("webdriver_file_detector")
        self._proxy = self._spec_import_if_not_none("webdriver_proxy")
        self._browser_profile = self._spec_import_if_not_none("webdriver_browser_profile")
        self._options = deepcopy(self._spec_import_if_not_none("webdriver_options"))

        # Required param
        self._capabilities = self._context.config.get("webdriver_capabilities")
        self._capabilities = spec_import(self._capabilities)

    def _spec_import_if_not_none(self, config_option):
        value = self._context.config.get(config_option, None)
        if value:
            value = spec_import(value)
        return value

    def _start(self):
        self._context.browser = self
        self._remote = SeleniumRemote(
            desired_capabilities=self._capabilities,
            command_executor=self._command_executor,
            browser_profile=self._browser_profile,
            proxy=self._proxy,
            keep_alive=self._keep_alive,
            file_detector=self._file_detector,
            options=self._options,
        )
        self._context.raw_webdriver = self._remote

    def _quit(self):
        if hasattr(self, "_remote"):
            self._remote.quit()

    def _browser_has_timing_capabilities(self):
        return self._remote.capabilities["browserName"] == "chrome"

    def _is_using_tls(self, name):
        return name.startswith("https")

    def _get_tls_timing(self, timings):
        if self._is_using_tls(timings["name"]):
            return timings["connectEnd"] - timings["secureConnectionStart"]
        logger.info("Secure TLS connection not used, defaulting tls_time to 0")
        return 0

    def _get_tcp_timing(self, timings):
        if self._is_using_tls(timings["name"]):
            return timings["secureConnectionStart"] - timings["connectStart"]
        else:
            return timings["connectEnd"] - timings["connectStart"]

    def _send_page_load_metrics(self):
        if not self._browser_has_timing_capabilities():
            return
        performance_entries = self._remote.execute_script(
            "return performance.getEntriesByType('navigation')"
        )

        paint_entries = self._remote.execute_script(
            "return performance.getEntriesByType('paint')"
        )

        _timings = self._extract_entries(performance_entries)
        timings = _timings[0] if _timings else None
        if timings:
            protocol = timings.get("nextHopProtocol")
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
        else:
            metrics = {}

        _paint_timings = self._extract_entries(paint_entries, expected=2)
        paint_timings = (
            self._format_paint_timings(_paint_timings) if _paint_timings else None
        )
        if paint_timings:
            metrics["first_contentful_paint"] = paint_timings["first-contentful-paint"]
            metrics["first_paint"] = paint_timings["first-paint"]

        if metrics:
            self._context.send(
                "selenium_page_load_metrics",
                **self._extract_and_convert_metrics_to_seconds(metrics),
            )

    def _extract_entries(self, entries, expected=1):
        if len(entries) == expected:
            return entries[:expected]
        logger.error(
            f"Performance entries did not return the expected count: expected {expected} - actual {len(entries)}"
        )
        return

    def _format_paint_timings(self, entries):
        return {metric["name"]: metric["startTime"] for metric in entries}

    def _extract_and_convert_metrics_to_seconds(self, metrics):
        converted_metrics = {}
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

    def wait_for_elements(self, locator, timeout=5):
        return self._wait_for(
            EC.presence_of_all_elements_located,
            locator,
            f"Timed out trying to find elements '{locator}' in the dom",
            timeout,
        )

    def wait_for_element(self, locator, timeout=5):
        return self._wait_for(
            EC.presence_of_element_located,
            locator,
            f"Timed out trying to find element '{locator}' in the dom",
            timeout,
        )

    def wait_for_url(self, locator, timeout=5):
        return self._wait_for(
            EC.url_to_be,
            locator,
            f"Timed out waiting for url to be '{locator}' in the dom",
            timeout,
        )

    def _wait_for(self, condition_func, locator, err_msg, timeout=5):
        try:
            return WebDriverWait(self._remote, timeout).until(condition_func(locator))
        except TimeoutException as te:
            raise MiteError(err_msg) from te

    def switch_to_default(self):
        self._remote.switch_to.default_content()

    def switch_to_iframe(self, locator):
        self._remote.switch_to.frame(self._remote.find_element(*locator))

    def switch_to_parent(self):
        self._remote.switch_to.parent_frame()

    @property
    def current_url(self):
        return self._remote.current_url


class JsMetricsContext:
    def __init__(self, browser):
        self._browser = browser
        self.results = None
        self.start_time = None
        self.execution_time = None

    async def __aenter__(self):
        self.start_time = time.time()
        self._browser._clear_resource_timings()

    async def __aexit__(self, exc_type, exc, tb):
        self.results = self._browser._retrieve_javascript_metrics()
        self.execution_time = time.time() - self.start_time


class _SeleniumWireWrapper(_SeleniumWrapper):
    def __init__(self, context):
        super().__init__(context)
        self._seleniumwire_options = (
            self._spec_import_if_not_none("seleniumwire_options") or {}
        )

    def _start(self):
        module = importlib.import_module("seleniumwire.webdriver")
        self._context.browser = self
        addr = socket.gethostbyname(socket.gethostname())
        self._remote = module.Remote(
            desired_capabilities=self._capabilities,
            command_executor=self._command_executor,
            browser_profile=self._browser_profile,
            proxy=self._proxy,
            keep_alive=self._keep_alive,
            file_detector=self._file_detector,
            options=self._options,
            seleniumwire_options={
                **self._seleniumwire_options,
                **{"addr": addr},
            },
        )
        logger.debug(f"Selenium-wire machine IP: {addr}")
        self._context.raw_webdriver = self._remote

    def wait_for_request(self, url, timeout=5):
        return self._remote.wait_for_request(url, timeout)

    @property
    def requests(self):
        return self._remote.requests

    def add_request_interceptor(self, request_interceptor):
        self._remote.request_interceptor = request_interceptor


@asynccontextmanager
async def _selenium_context_manager(context, wire):
    sw = _SeleniumWireWrapper(context) if wire else _SeleniumWrapper(context)
    try:
        sw._start()
        yield
    finally:
        sw._quit()


def mite_selenium(*args, wire=False):
    def wrapper_factory(func):
        if wire:
            try:
                importlib.import_module("seleniumwire.webdriver")
            except ModuleNotFoundError:
                raise Exception(
                    "The wire=True argument to mite_selenium is only supported "
                    + "if mite was installed with the 'selenium_wire' extra"
                )

        @wraps(func)
        async def wrapper(ctx, *args, **kwargs):
            async with _selenium_context_manager(ctx, wire):
                return await func(ctx, *args, **kwargs)

        return wrapper

    if len(args) == 0:
        # invoked as @mite_selenium(wire=...) def foo(...)
        return wrapper_factory
    elif len(args) > 1:
        raise Exception("Anomalous invocation of mite_welenium decorator")
    else:
        # len(args) == 1; invoked as @mite_selenium def foo(...)
        return wrapper_factory(args[0])
