from unittest.mock import call, patch

import pytest
from mocks.mock_context import MockContext
from mocks.mock_selenium import mock_paint_times, mock_performance_times
from selenium.common.exceptions import TimeoutException

from mite.exceptions import MiteError
from mite_selenium import _SeleniumWrapper, mite_selenium

EXAMPLE_WEBDRIVER_CONFIG = {
    "webdriver_command_executor": "http://127.0.0.1:4444/wd/test",
    "webdriver_keep_alive": True,
    "webdriver_file_detector": "mocks.mock_selenium:file_detector",
    "webdriver_proxy": "mocks.mock_selenium:proxy",
    "webdriver_browser_profile": "mocks.mock_selenium:browser_profile",
    "webdriver_options": "mocks.mock_selenium:options",
    "webdriver_capabilities": "mocks.mock_selenium:capabilities",
}

LIGHTWEIGHT_WEBDRIVER_CONFIG = {
    "webdriver_capabilities": "mocks.mock_selenium:capabilities"
}


# Mock webdriver capabilities with spec import
webdriver_capabilities = {"browser": "Chrome"}
DICT_CAPABILITIES_CONFIG = {
    "webdriver_capabilities": "test_webdriver:webdriver_capabilities"
}


def test_config_loaded():
    context = MockContext()
    context.config = EXAMPLE_WEBDRIVER_CONFIG
    wrapper = _SeleniumWrapper(context)
    assert wrapper._keep_alive is True
    assert wrapper._file_detector is True
    assert wrapper._proxy is True
    assert wrapper._browser_profile is True
    assert wrapper._options is True
    assert wrapper._capabilities is True


def test_config_defaults():
    context = MockContext()
    context.config = LIGHTWEIGHT_WEBDRIVER_CONFIG
    wrapper = _SeleniumWrapper(context)
    assert wrapper._keep_alive is False
    assert wrapper._file_detector is None
    assert wrapper._proxy is None
    assert wrapper._browser_profile is None
    assert wrapper._options is None
    assert wrapper._capabilities is True


def test_webdriver_capabilities_as_dict():
    wrapper = _setup_wrapper(DICT_CAPABILITIES_CONFIG)
    assert wrapper._capabilities == {"browser": "Chrome"}


@patch("mite_selenium.SeleniumRemote", autospec=True)
def test_webdriver_start_stop(MockRemote):
    wrapper = _setup_wrapper(DICT_CAPABILITIES_CONFIG)
    wrapper._start()
    MockRemote.assert_called_with(
        browser_profile=None,
        command_executor=wrapper._command_executor,
        desired_capabilities={"browser": "Chrome"},
        file_detector=None,
        keep_alive=False,
        options=None,
        proxy=None,
    )
    wrapper._quit()
    # For some reason, calling the Mock provides a reference to the instance
    # that was created when the mock was previously instantiated
    MockRemote().quit.assert_called()


def test_get_js_metrics_context():
    wrapper = _setup_wrapper(DICT_CAPABILITIES_CONFIG)
    context = wrapper.get_js_metrics_context()
    assert context._browser == wrapper
    assert context.results is None


@pytest.mark.asyncio
async def test_js_metrics_context_manager():
    wrapper = _setup_wrapper(DICT_CAPABILITIES_CONFIG)
    with patch("mite_selenium.SeleniumRemote") as mock_remote:
        wrapper._start()
        js_context = wrapper.get_js_metrics_context()

        async with js_context:
            pass

        calls = [
            call("performance.clearResourceTimings()"),
            call("return performance.getEntriesByType('resource')"),
        ]
        mock_remote.return_value.execute_script.assert_has_calls(calls)


def test_wait_for_element():
    wrapper = _setup_wrapper(DICT_CAPABILITIES_CONFIG)
    with patch("mite_selenium.SeleniumRemote") as mock_remote, patch(
        "mite_selenium.WebDriverWait"
    ) as mock_web_driver_wait, patch("mite_selenium.EC") as mock_ec:
        wrapper._start()
        locator = ("foo", "bar")
        wrapper.wait_for_element(locator, timeout=7)

        mock_web_driver_wait.assert_called_once_with(mock_remote.return_value, 7)
        mock_web_driver_wait.return_value.until.assert_called_once_with(
            mock_ec.presence_of_element_located.return_value
        )
        mock_ec.presence_of_element_located.assert_called_once_with(locator)


def test_wait_for_element_raises_timeout_exception():
    wrapper = _setup_wrapper(DICT_CAPABILITIES_CONFIG)
    with patch("mite_selenium.SeleniumRemote"), patch(
        "mite_selenium.WebDriverWait"
    ) as mock_web_driver_wait, patch("mite_selenium.EC"):
        wrapper._start()
        locator = ("foo", "bar")
        mock_web_driver_wait.return_value.until.side_effect = TimeoutException
        with pytest.raises(MiteError, match="Timed out trying to find element"):
            wrapper.wait_for_element(locator, timeout=7)


def test_wait_for_elements():
    wrapper = _setup_wrapper(DICT_CAPABILITIES_CONFIG)
    with patch("mite_selenium.SeleniumRemote") as mock_remote, patch(
        "mite_selenium.WebDriverWait"
    ) as mock_web_driver_wait, patch("mite_selenium.EC") as mock_ec:
        wrapper._start()
        locator = ("foo", "bar")
        wrapper.wait_for_elements(locator, timeout=7)

        mock_web_driver_wait.assert_called_once_with(mock_remote.return_value, 7)
        mock_web_driver_wait.return_value.until.assert_called_once_with(
            mock_ec.presence_of_all_elements_located.return_value
        )
        mock_ec.presence_of_all_elements_located.assert_called_once_with(locator)


def test_wait_for_elements_raises_timeout_exception():
    wrapper = _setup_wrapper(DICT_CAPABILITIES_CONFIG)
    with patch("mite_selenium.SeleniumRemote"), patch(
        "mite_selenium.WebDriverWait"
    ) as mock_web_driver_wait, patch("mite_selenium.EC"):
        wrapper._start()
        locator = ("foo", "bar")
        mock_web_driver_wait.return_value.until.side_effect = TimeoutException
        with pytest.raises(MiteError, match="Timed out trying to find elements"):
            wrapper.wait_for_elements(locator, timeout=7)


def test_wait_for_url():
    wrapper = _setup_wrapper(DICT_CAPABILITIES_CONFIG)
    with patch("mite_selenium.SeleniumRemote") as mock_remote, patch(
        "mite_selenium.WebDriverWait"
    ) as mock_web_driver_wait, patch("mite_selenium.EC") as mock_ec:
        wrapper._start()
        locator = "https://google.com"
        wrapper.wait_for_url(locator, timeout=7)

        mock_web_driver_wait.assert_called_once_with(mock_remote.return_value, 7)
        mock_web_driver_wait.return_value.until.assert_called_once_with(
            mock_ec.url_to_be.return_value
        )
        mock_ec.url_to_be.assert_called_once_with(locator)


def test_wait_for_url_raises_timeout_exception():
    wrapper = _setup_wrapper(DICT_CAPABILITIES_CONFIG)
    with patch("mite_selenium.SeleniumRemote"), patch(
        "mite_selenium.WebDriverWait"
    ) as mock_web_driver_wait, patch("mite_selenium.EC"):
        wrapper._start()
        locator = "https://google.com"
        mock_web_driver_wait.return_value.until.side_effect = TimeoutException
        with pytest.raises(MiteError, match="Timed out waiting for url to be"):
            wrapper.wait_for_url(locator, timeout=7)


def test_webdriver_get():
    wrapper = _setup_wrapper(DICT_CAPABILITIES_CONFIG)
    with patch("mite_selenium.SeleniumRemote") as mock_remote:
        mock_remote.return_value.capabilities = {"browserName": "chrome"}
        mock_remote.return_value.execute_script.side_effect = [
            mock_performance_times,
            mock_paint_times,
        ]
        wrapper._start()
        wrapper.get("https://google.com")

        mock_remote.assert_called()
        mock_remote.return_value.get.assert_called_with("https://google.com")
        mock_remote.return_value.execute_script.assert_called()
        assert wrapper._remote == mock_remote.return_value


@pytest.mark.asyncio
async def test_selenium_context_manager():
    context = MockContext()
    context.config = DICT_CAPABILITIES_CONFIG

    @mite_selenium
    async def test(context):
        pass

    # patch with async decorator misbehaving
    with patch("mite_selenium.SeleniumRemote", autospec=True) as mock_remote:
        await test(context)

    mock_remote.assert_called()
    mock_remote().quit.assert_called()


@pytest.mark.asyncio
async def test_selenium_context_manager_with_parens():
    context = MockContext()
    context.config = DICT_CAPABILITIES_CONFIG

    @mite_selenium()
    async def test(context):
        pass

    # patch with async decorator misbehaving
    with patch("mite_selenium.SeleniumRemote", autospec=True) as mock_remote:
        await test(context)

    mock_remote.assert_called()
    mock_remote().quit.assert_called()


def _setup_wrapper(capabilites):
    context = MockContext()
    context.config = capabilites
    return _SeleniumWrapper(context)
