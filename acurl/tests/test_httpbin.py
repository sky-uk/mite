import pytest
import acurl
import asyncio
from urllib.parse import urlencode
import inspect
import requests
import pytest
# Pre-test connectivity check for httpbin
def is_httpbin_reachable(httpbin_url):
    try:
        resp = requests.get(f"{httpbin_url}/ip", timeout=5)
        return resp.status_code == 200
    except Exception as e:
        print(f"[ERROR] httpbin not reachable: {e}")
        return False
import psutil
import os







async def session():
    el = acurl.CurlWrapper(asyncio.get_running_loop())
    return el.session()


@pytest.mark.asyncio
async def test_get(httpbin):
    if not is_httpbin_reachable(httpbin.url):
        pytest.skip("httpbin is not reachable from CI environment.")
    process = psutil.Process(os.getpid())
    print(f"[DEBUG] Memory usage before test_get: {process.memory_info().rss / 1024 ** 2:.2f} MB")
    print(f"[DEBUG] httpbin.url = {httpbin.url}")
    s = await session()
    try:
        r = await asyncio.wait_for(s.get(f"{httpbin.url}/ip"), timeout=10)
        print(f"[DEBUG] GET /ip status: {r.status_code}, headers: {r.headers}, body: {r.text if hasattr(r, 'text') else r.content}")
        assert r.status_code == 200
        assert isinstance(r.headers, dict)
        assert isinstance(r.json(), dict)
        print(f"[DEBUG] Memory usage after GET /ip: {process.memory_info().rss / 1024 ** 2:.2f} MB")
    except Exception as e:
        print(f"[ERROR] Exception in test_get: {e}")
        raise
    finally:
        if hasattr(s, "close"):
            await maybe_await(s.close())
    print(f"[DEBUG] Memory usage after test_get: {process.memory_info().rss / 1024 ** 2:.2f} MB")


@pytest.mark.asyncio
@pytest.fixture
async def test_cookies(httpbin, acurl_session):
    r = await acurl_session.get(f"{httpbin.url}/cookies/set?name=value")
    assert r.cookies == {"name": "value"}


@pytest.mark.asyncio
@pytest.fixture
async def test_session_cookies(httpbin, acurl_session):
    await acurl_session.get(f"{httpbin.url}/cookies/set?name=value")
    cookies = acurl_session.cookies()
    assert cookies == {"name": "value"}
    acurl_session.erase_all_cookies()
    cookie_list = acurl_session.cookies()
    assert len(cookie_list) == 0


@pytest.mark.asyncio
async def test_session_cookies_sent_on_subsequent_request(httpbin):
    if not is_httpbin_reachable(httpbin.url):
        pytest.skip("httpbin is not reachable from CI environment.")
    print(f"[DEBUG] httpbin.url = {httpbin.url}")
    s = await session()
    try:
        set_resp = await asyncio.wait_for(s.get(f"{httpbin.url}/cookies/set?name=value"), timeout=10)
        print(f"[DEBUG] Set cookie response: {set_resp.status_code}, {set_resp.headers}")
        resp = await asyncio.wait_for(s.get(f"{httpbin.url}/cookies"), timeout=10)
        print(f"[DEBUG] Cookies response: {resp.status_code}, {resp.headers}, {resp.text if hasattr(resp, 'text') else resp.content}")
        data = resp.json()
        assert len(data) == 1
        assert data["cookies"] == {"name": "value"}
    except Exception as e:
        print(f"[ERROR] Exception in test_session_cookies_sent_on_subsequent_request: {e}")
        raise
    finally:
        if hasattr(s, "close"):
            await maybe_await(s.close())


@pytest.mark.asyncio
async def test_set_cookies(httpbin):
    if not is_httpbin_reachable(httpbin.url):
        pytest.skip("httpbin is not reachable from CI environment.")
    print(f"[DEBUG] httpbin.url = {httpbin.url}")
    s = await session()
    try:
        resp1 = await asyncio.wait_for(s.get(f"{httpbin.url}/cookies/set?name=value"), timeout=10)
        print(f"[DEBUG] Set cookie1 response: {resp1.status_code}, {resp1.headers}")
        r = await asyncio.wait_for(
            s.get(f"{httpbin.url}/cookies/set?name2=value", cookies={"name3": "value"}), timeout=10
        )
        print(f"[DEBUG] Set cookie2 response: {r.status_code}, {r.headers}, cookies: {r.cookies}")
        assert r.cookies == {"name": "value", "name2": "value", "name3": "value"}
    except Exception as e:
        print(f"[ERROR] Exception in test_set_cookies: {e}")
        raise
    finally:
        if hasattr(s, "close"):
            await maybe_await(s.close())


@pytest.mark.asyncio
async def test_basic_auth(httpbin):
    if not is_httpbin_reachable(httpbin.url):
        pytest.skip("httpbin is not reachable from CI environment.")
    print(f"[DEBUG] httpbin.url = {httpbin.url}")
    s = await session()
    try:
        r = await asyncio.wait_for(
            s.get(f"{httpbin.url}/basic-auth/user/password", auth=("user", "password")), timeout=10
        )
        print(f"[DEBUG] Basic auth response: {r.status_code}, {r.headers}")
        assert r.status_code == 200
    except Exception as e:
        print(f"[ERROR] Exception in test_basic_auth: {e}")
        raise
    finally:
        if hasattr(s, "close"):
            await maybe_await(s.close())


@pytest.mark.asyncio
async def test_failed_basic_auth(httpbin):
    if not is_httpbin_reachable(httpbin.url):
        pytest.skip("httpbin is not reachable from CI environment.")
    print(f"[DEBUG] httpbin.url = {httpbin.url}")
    s = await session()
    try:
        r = await asyncio.wait_for(
            s.get(f"{httpbin.url}/basic-auth/user/password", auth=("notuser", "notpassword")), timeout=10
        )
        print(f"[DEBUG] Failed basic auth response: {r.status_code}, {r.headers}")
        assert r.status_code == 401
    except Exception as e:
        print(f"[ERROR] Exception in test_failed_basic_auth: {e}")
        raise
    finally:
        if hasattr(s, "close"):
            await maybe_await(s.close())


@pytest.mark.asyncio
async def test_redirect(httpbin):
    if not is_httpbin_reachable(httpbin.url):
        pytest.skip("httpbin is not reachable from CI environment.")
    print(f"[DEBUG] httpbin.url = {httpbin.url}")
    s = await session()
    try:
        url = f"{httpbin.url}/ip"
        r = await asyncio.wait_for(s.get(f"{httpbin.url}/redirect-to?" + urlencode({"url": url})), timeout=10)
        print(f"[DEBUG] Redirect response: {r.status_code}, {r.headers}, url: {r.url}")
        assert r.url == url
    except Exception as e:
        print(f"[ERROR] Exception in test_redirect: {e}")
        raise
    finally:
        if hasattr(s, "close"):
            await maybe_await(s.close())

async def maybe_await(obj):
    if inspect.isawaitable(obj):
        return await obj
    return obj
