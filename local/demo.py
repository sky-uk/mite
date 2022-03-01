from mite.scenario import StopScenario
from mite_http import mite_http
from mite_selenium import mite_selenium

import asyncio

class Browser:
    def __init__(self, context):
        self._context = context
        self.browser = self._context.browser

    async def get_url1(self, **kwargs):
        async with self._context.transaction("Get 'url1' Page"):
            self.browser.get("http://10.88.58.62:14301/url1")

    async def get_url2(self, **kwargs):
        async with self._context.transaction("Get 'url2' Page"):
            self.browser.get("http://10.88.58.62:14301/url2")


def volume_model_factory(n):
    def vm(start, end):
        if start > 60 * 15:  # Will run for 15 mins
            raise StopScenario
        return n

    vm.__name__ = f"volume model {n}"
    return vm


@mite_selenium
@mite_http
async def get_url1(context):
    await asyncio.sleep(60)
    browser = Browser(context)

    await browser.get_url1()
    # await browser.browser.close()

@mite_selenium
@mite_http
async def get_url2(context):
    await asyncio.sleep(60)
    browser = Browser(context)

    await browser.get_url2()
    # await browser.browser.close()


@mite_http
async def get_url1_sans_sel(ctx):
    async with ctx.transaction("Get 'url1' Page sans selenium"):
        await asyncio.sleep(5)
        await ctx.http.get("http://10.88.58.62:14301/url1")


@mite_http
async def get_url2_sans_sel(ctx):
    async with ctx.transaction("Get 'url2' Page sans selenium"):
        await asyncio.sleep(5)
        await ctx.http.get("http://10.88.58.62:14301/url2")


def scenario():
    return [
        # ["local.demo:get_url1", None, volume_model_factory(5)],
        # ["local.demo:get_url2", None, volume_model_factory(5)],
        ["local.demo:get_url1_sans_sel", None, volume_model_factory(5)],
        ["local.demo:get_url2_sans_sel", None, volume_model_factory(5)],
    ]







# Selenium stuff

from selenium.webdriver.chrome.options import Options
from mite.config import default_config_loader


def set_webdriver_options(headless=True):
    options = Options()
    # Set to True for automated testing when you don't need to be able to see the page
    # Set to False for testing locally if you want to be able to see the page
    options.headless = headless

    return options


chrome_webdriver_capabilities = {"browserName": "chrome"}
webdriver_options_headless_off = set_webdriver_options(False)
webdriver_options_headless_on = set_webdriver_options(True)
seleniumwire_options = {}


def set_options(webdriver_headless=True):

    if webdriver_headless:
        webdriver_options = "webdriver_options_headless_on"
    else:
        webdriver_options = "webdriver_options_headless_off"

    config = {
        "webdriver_capabilities": "local.demo:chrome_webdriver_capabilities",
        "webdriver_options": f"local.demo:{webdriver_options}",
        "seleniumwire_options": "local.demo:seleniumwire_options",
    }
    default_config = default_config_loader()
    config.update(default_config)
    return config


def config():
    return {
        "webdriver_command_executor": "http://10.88.58.62:4444/wd/hub",
        **set_options(webdriver_headless=True),
    }

