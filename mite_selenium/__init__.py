import asyncio
import logging

from selenium.webdriver import Remote
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
                "webdriver_command_executor",
                "http://127.0.0.1:4444/wd/hub")
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
                options=self._options)

    def stop(self):
        self._context.browser.close()


class _SeleniumContextManager:
    def __init__(self, context):
        self._context = context
        self._webdriver = _SeleniumWrapper(context)

    async def __aenter__(self):
        self._webdriver.start()

    async def __aexit__(self, *args):
        self._webdriver.stop()


def mite_selenium(func):
    async def wrapper(ctx, *args, **kwargs):
        async with _SeleniumContextManager(ctx):
            return await func(ctx, *args, **kwargs)
    return wrapper

