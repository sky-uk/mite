import acurl
import asyncio
from urllib.parse import urlencode
import pytest

def session():
    el = acurl.EventLoop()
    return el.session()


@pytest.mark.asyncio
async def test_get():
    s = session()
    r = await s.get('https://httpbin.org/ip')
    assert r.status_code == 200
    assert isinstance(r.headers, dict)
    # FIXME: is this a method in the requests api?
    assert isinstance(r.json(), dict)


@pytest.mark.asyncio
async def test_cookies():
    s = session()
    r = await s.get('https://httpbin.org/cookies/set?name=value')
    assert r.cookies == {'name': 'value'}


@pytest.mark.asyncio
async def test_session_cookies():
    s = session()
    r = await s.get('https://httpbin.org/cookies/set?name=value')
    cookie_list = await s.get_cookie_list()
    assert len(cookie_list) == 1
    assert cookie_list[0].name == 'name'
    await s.erase_all_cookies()
    cookie_list = await s.get_cookie_list()
    assert len(cookie_list) == 0


@pytest.mark.asyncio
async def test_set_cookies():
    s = session()
    await s.get('https://httpbin.org/cookies/set?name=value')
    r = await s.get('https://httpbin.org/cookies/set?name2=value', cookies={'name3': 'value'})
    assert r.cookies == {'name': 'value', 'name2': 'value', 'name3': 'value'}


@pytest.mark.asyncio
async def test_basic_auth():
    s = session()
    r = await s.get('https://httpbin.org/basic-auth/user/password', auth=('user', 'password'))
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_failed_basic_auth():
    s = session()
    r = await s.get('https://httpbin.org/basic-auth/user/password', auth=('notuser', 'notpassword'))
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_redirect():
    s = session()
    url = 'https://httpbin.org/ip'
    r = await s.get('https://httpbin.org/redirect-to?' + urlencode({'url': url}))
    assert r.url == url
