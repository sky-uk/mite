import asyncio
from urllib.parse import urlencode

import pytest

import acurl


async def session():
    el = acurl.CurlWrapper(asyncio.get_running_loop())
    return el.session()


@pytest.mark.asyncio
async def test_get(httpbin):
    s = await session()
    r = await s.get(f"{httpbin.url}/ip")
    assert r.status_code == 200
    assert isinstance(r.headers, dict)
    # FIXME: is this a method in the requests api?
    assert isinstance(r.json(), dict)


@pytest.mark.asyncio
async def test_cookies(httpbin, acurl_session):
    r = await acurl_session.get(f"{httpbin.url}/cookies/set?name=value")
    assert r.cookies == {"name": "value"}


@pytest.mark.asyncio
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
    await s.get(f"{httpbin.url}/cookies/set?name=value")
    resp = await s.get(f"{httpbin.url}/cookies")
    data = resp.json()
    assert len(data) == 1
    assert data["cookies"] == {"name": "value"}


@pytest.mark.asyncio
async def test_set_cookies(httpbin):
    s = await session()
    await s.get(f"{httpbin.url}/cookies/set?name=value")
    r = await s.get(f"{httpbin.url}/cookies/set?name2=value", cookies={"name3": "value"})
    assert r.cookies == {"name": "value", "name2": "value", "name3": "value"}


@pytest.mark.asyncio
async def test_basic_auth(httpbin):
    s = await session()
    r = await s.get(f"{httpbin.url}/basic-auth/user/password", auth=("user", "password"))
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_failed_basic_auth(httpbin):
    s = await session()
    r = await s.get(
        f"{httpbin.url}/basic-auth/user/password", auth=("notuser", "notpassword")
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_redirect(httpbin):
    s = await session()
    url = f"{httpbin.url}/ip"
    r = await s.get(f"{httpbin.url}/redirect-to?" + urlencode({"url": url}))
    assert r.url == url
