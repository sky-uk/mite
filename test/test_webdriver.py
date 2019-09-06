from unittest.mock import patch

import pytest

from mocks.mock_context import MockContext
from mite_selenium import _SeleniumWrapper, mite_selenium

EXAMPLE_WEBDRIVER_CONFIG = {
        "webdriver_command_executor" : "http://127.0.0.1:4444/wd/test",
        "webdriver_keep_alive" : True,
        "webdriver_file_detector" : "mocks.mock_selenium:file_detector",
        "webdriver_proxy" : "mocks.mock_selenium:proxy",
        "webdriver_browser_profile" : "mocks.mock_selenium:browser_profile",
        "webdriver_options" : "mocks.mock_selenium:options",
        "webdriver_capabilities" : "mocks.mock_selenium:capabilities",
}

LIGHTWEIGHT_WEBDRIVER_CONFIG = {
        "webdriver_capabilities" : "mocks.mock_selenium:capabilities"
        }

DICT_CAPABILITIES_CONFIG = {
        "webdriver_capabilities" : {"browser": "Chrome"}
        }


def test_config_loaded():
    context=MockContext()
    context.config = EXAMPLE_WEBDRIVER_CONFIG
    wrapper = _SeleniumWrapper(context)
    assert wrapper._command_executor == "http://127.0.0.1:4444/wd/test"
    assert wrapper._keep_alive == True
    assert wrapper._file_detector == True
    assert wrapper._proxy == True
    assert wrapper._browser_profile == True
    assert wrapper._options == True
    assert wrapper._capabilities == True


def test_config_defaults():
    context=MockContext()
    context.config = LIGHTWEIGHT_WEBDRIVER_CONFIG
    wrapper = _SeleniumWrapper(context)
    assert wrapper._command_executor == "http://127.0.0.1:4444/wd/hub"
    assert wrapper._keep_alive == False
    assert wrapper._file_detector is None
    assert wrapper._proxy is None
    assert wrapper._browser_profile is None
    assert wrapper._options is None
    assert wrapper._capabilities == True


def test_webdriver_capabilities_as_dict():
    context=MockContext()
    context.config = DICT_CAPABILITIES_CONFIG
    wrapper = _SeleniumWrapper(context)
    assert wrapper._capabilities == {"browser": "Chrome"}


@patch("mite_selenium.Remote", autospec=True)
def test_webdriver_start_stop(MockRemote):
    context=MockContext()
    context.config = DICT_CAPABILITIES_CONFIG
    wrapper = _SeleniumWrapper(context)  
    wrapper.start()
    MockRemote.assert_called_with(
            browser_profile=None,
            command_executor='http://127.0.0.1:4444/wd/hub',
            desired_capabilities={'browser': 'Chrome'},
            file_detector=None,
            keep_alive=False,
            options=None,
            proxy=None)
    wrapper.stop()
    # For some reason, calling the Mock provides a reference to the instance
    # that was created when the mock was previously instantiated
    MockRemote().close.assert_called()


@pytest.mark.asyncio
async def test_selenium_context_manager():
    context=MockContext()
    context.config = DICT_CAPABILITIES_CONFIG

    @mite_selenium
    async def test(context):
        pass    

    # patch with async decorator misbehaving
    with patch('mite_selenium.Remote', autospec=True) as MockRemote:
        await test(context)

    MockRemote.assert_called()
    MockRemote().close.assert_called()

