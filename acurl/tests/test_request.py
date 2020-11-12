from unittest.mock import Mock

import pytest
from helpers import create_request

import acurl


def session():
    el = acurl.EventLoop()
    return el.session()


def test_request_headers():
    r = create_request("GET", "http://foo.com", headers=["Foo: bar", "Baz: quux"])
    assert "Foo" in r.headers
    assert r.headers["Foo"] == "bar"
    assert "Baz" in r.headers
    assert r.headers["Baz"] == "quux"


def test_request_cookies():
    session_mock = Mock()
    session_mock.get_cookie_list.return_value = ()
    r = create_request(
        "GET",
        "http://foo.com",
        cookies=(
            acurl.parse_cookie_string(
                "foo.com\tFALSE\t/bar\tFALSE\t0\tmy_cookie\tmy_value"
            ),
            acurl.parse_cookie_string("foo.com\tFALSE\t/bar\tFALSE\t0\tfoo\tbar"),
        ),
    )
    assert "my_cookie" in r.cookies
    assert r.cookies["my_cookie"] == "my_value"
    assert "foo" in r.cookies
    assert r.cookies["foo"] == "bar"


@pytest.mark.asyncio
async def test_request_cookies_from_previous(httpbin):
    s = session()
    await s.get(httpbin.url + "/cookies/set?name=value")
    r = await s.get(httpbin.url + "/get")
    assert r.request.cookies == {"name": "value"}


@pytest.mark.asyncio
@pytest.mark.slow
async def test_request_cookies_from_previous_excludes_other_domains(httpbin):
    s = session()
    await s.get(httpbin.url + "/cookies/set?name=value")
    # FIXME: we want to set a cookie for another domain.  There's no easy way
    # to get another domain set up loally, so we (as an exception) go out to
    # the network for this test.
    await s.get("https://httpbin.org/cookies/set?foo=bar")
    r = await s.get(httpbin.url + "/get")
    assert r.request.cookies == {"name": "value"}
