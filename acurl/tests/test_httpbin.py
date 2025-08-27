import pytest
import acurl


# Print tracemalloc stats after each test
@pytest.fixture(autouse=True)
def tracemalloc_report():
    yield
    current, peak = tracemalloc.get_traced_memory()
    print(f"[tracemalloc] Current memory usage: {current / 1024:.1f} KiB; Peak: {peak / 1024:.1f} KiB")

import tracemalloc
tracemalloc.start()

import asyncio
from urllib.parse import urlencode
import pytest
import acurl
def print_tracemalloc_stats():
    current, peak = tracemalloc.get_traced_memory()
    print(f"[tracemalloc] Current memory usage: {current / 1024:.1f} KiB; Peak: {peak / 1024:.1f} KiB")


async def session():
    el = acurl.CurlWrapper(asyncio.get_running_loop())
    return el.session()


@pytest.mark.asyncio
async def test_get(httpbin):
    s = await session()
    try:
        r = await s.get(f"{httpbin.url}/ip")
        assert r.status_code == 200
        assert isinstance(r.headers, dict)
        assert isinstance(r.json(), dict)
    finally:
        if hasattr(s, "close"):
            await maybe_await(s.close())


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
    s = await session()
    try:
        await s.get(f"{httpbin.url}/cookies/set?name=value")
        resp = await s.get(f"{httpbin.url}/cookies")
        data = resp.json()
        assert len(data) == 1
        assert data["cookies"] == {"name": "value"}
    finally:
        if hasattr(s, "close"):
            await maybe_await(s.close())


@pytest.mark.asyncio
async def test_set_cookies(httpbin):
    s = await session()
    try:
        await s.get(f"{httpbin.url}/cookies/set?name=value")
        r = await s.get(
            f"{httpbin.url}/cookies/set?name2=value", cookies={"name3": "value"}
        )
        assert r.cookies == {"name": "value", "name2": "value", "name3": "value"}
    finally:
        if hasattr(s, "close"):
            await maybe_await(s.close())


@pytest.mark.asyncio
async def test_basic_auth(httpbin):
    s = await session()
    try:
        r = await s.get(
            f"{httpbin.url}/basic-auth/user/password", auth=("user", "password")
        )
        assert r.status_code == 200
    finally:
        if hasattr(s, "close"):
            await maybe_await(s.close())


@pytest.mark.asyncio
async def test_failed_basic_auth(httpbin):
    s = await session()
    try:
        r = await s.get(
            f"{httpbin.url}/basic-auth/user/password", auth=("notuser", "notpassword")
        )
        assert r.status_code == 401
    finally:
        if hasattr(s, "close"):
            await maybe_await(s.close())


@pytest.mark.asyncio
async def test_redirect(httpbin):
    s = await session()
    try:
        url = f"{httpbin.url}/ip"
        r = await s.get(f"{httpbin.url}/redirect-to?" + urlencode({"url": url}))
        assert r.url == url
    finally:
        if hasattr(s, "close"):
            await maybe_await(s.close())
import inspect
async def maybe_await(obj):
    if inspect.isawaitable(obj):
        return await obj
    return obj
