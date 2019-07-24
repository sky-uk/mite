import acurl
import asyncio
from urllib.parse import urlencode


def session():
    el = acurl.EventLoop()
    return el.session()


def _await(awaitable):
    return asyncio.get_event_loop().run_until_complete(awaitable)


def test_get():
    s = session()
    r = _await(s.get('https://httpbin.org/ip'))
    r.status_code
    r.headers
    r.json


def test_cookies():
    s = session()
    r = _await(s.get('https://httpbin.org/cookies/set?name=value'))
    assert r.cookies == {'name': 'value'}


def test_session_cookies():
    s = session()
    r = _await(s.get('https://httpbin.org/cookies/set?name=value'))
    cookie_list = _await(s.get_cookie_list())
    assert len(cookie_list) == 1
    assert cookie_list[0].name == 'name'
    _await(s.erase_all_cookies())
    cookie_list = _await(s.get_cookie_list())
    assert len(cookie_list) == 0


def test_set_cookies():
    s = session()
    r = _await(s.get('https://httpbin.org/cookies/set?name=value'))
    r = _await(s.get('https://httpbin.org/cookies/set?name2=value', cookies={'name3': 'value'}))
    assert r.cookies == {'name': 'value', 'name2': 'value', 'name3': 'value'}


def test_basic_auth():
    s = session()
    r = _await(s.get('https://httpbin.org/basic-auth/user/password', auth=('user', 'password')))
    assert r.status_code == 200


def test_failed_basic_auth():
    s = session()
    r = _await(s.get('https://httpbin.org/basic-auth/user/password', auth=('notuser', 'notpassword')))
    assert r.status_code == 401


def test_redirect():
    s = session()
    url = 'https://httpbin.org/ip'
    r = _await(s.get('https://httpbin.org/redirect-to?' + urlencode({'url': url})))
    assert r.url == url

    
