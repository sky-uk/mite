import logging
from contextlib import asynccontextmanager

from mite.stats import Counter, Histogram, Stats, label_extractor, matcher_by_type
from mite.utils import spec_import
from selenium.webdriver import Remote

logger = logging.getLogger(__name__)


_MITE_STATS = (
    Histogram(
        'mite_http_selenium_response_time_seconds',
        matcher_by_type('http_selenium_metrics'),
        label_extractor=label_extractor(['transaction']),
        value_extractor=lambda x: x['total_time'],
        bins=[0.0001, 0.001, 0.01, 0.05, 0.1, 0.2, 0.4, 0.8, 1, 2, 4, 8, 16, 32, 64],
    ),
    Counter(
        'mite_http_selenium_response_total',
        matcher_by_type('http_selenium_metrics'),
        label_extractor('test journey transaction'.split()),
    ),
)
Stats.register(_MITE_STATS)


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
        self._capabilities = self._context.config.get('webdriver_capabilities')
        if not type(self._capabilities) == dict:
            self._capabilities = spec_import(self._capabilities)

    def _spec_import_if_none(self, config_option):
        value = self._context.config.get(config_option, None)
        if value:
            value = spec_import(value)
        return value

    def start(self):
        self._context.browser = Remote(
            desired_capabilities=self._capabilities,
            command_executor=self._command_executor,
            browser_profile=self._browser_profile,
            proxy=self._proxy,
            keep_alive=self._keep_alive,
            file_detector=self._file_detector,
            options=self._options,
        )

    def stop(self):
        self._context.browser.close()


def send_selenium_times(context):
    """Maybe would probably need more error handling
    if somebody tried to use with an incompatible browser"""
    if context.browser.capabilities['browserName'] != 'chrome':
        logger.warning(
            'Timing metrics in %s are not currently supported',
            context.browser.capabilities['browserName'],
        )
        return

    timings = context.browser.execute_script(
        'return performance.getEntriesByType("navigation")'
    )[0]
    context.send(
        "http_selenium_metrics",
        dom_complete=timings["domComplete"],
        dom_interactive=timings["domInteractive"],
        transfer_size=timings["transferSize"],
        transfer_start_timings=["requestStart"],
        tls_time=timings["secureConnectionStart"],
        dns_time=timings["domainLookupEnd"],
        connect_time=timings["connectEnd"],
        total_time=timings["duration"],
        effective_url=timings["name"],
    )


@asynccontextmanager
async def _selenium_context_manager(context):
    try:
        sw = _SeleniumWrapper(context)
        sw.start()
        yield
    finally:
        sw.stop()


def mite_selenium(func):
    async def wrapper(ctx, *args, **kwargs):
        async with _selenium_context_manager(ctx):
            return await func(ctx, *args, **kwargs)

    return wrapper
