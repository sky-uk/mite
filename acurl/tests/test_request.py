from unittest.mock import Mock

import pytest
from helpers import create_request

import acurl


def test_request_headers():
    r = create_request("GET", "http://foo.com", headers=("Foo: bar", "Baz: quux"))
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
            acurl._Cookie(False, "foo.com", True, "/", False, 0, "foo", "bar").format(),
            acurl._Cookie(
                False, "foo.com", True, "/", False, 0, "my_cookie", "my_value"
            ).format(),
        ),
    )
    assert "my_cookie" in r.cookies
    assert r.cookies["my_cookie"] == "my_value"
    assert "foo" in r.cookies
    assert r.cookies["foo"] == "bar"


@pytest.mark.asyncio
async def test_request_e2e(httpbin, acurl_session):
    r = await acurl_session.get(
        f"{httpbin.url}/get", headers={"Foo": "bar"}, cookies={"baz": "quux"}
    )
    assert r.request.cookies == {"baz": "quux"}
    assert r.request.headers == {"Foo": "bar"}


@pytest.mark.asyncio
async def test_request_cookies_from_previous(httpbin, acurl_session):
    await acurl_session.get(f"{httpbin.url}/cookies/set?name=value")
    r = await acurl_session.get(f"{httpbin.url}/get", cookies={"foo": "bar"})
    assert r.request.cookies == {"name": "value", "foo": "bar"}


@pytest.mark.asyncio
@pytest.mark.slow
async def test_request_cookies_from_previous_excludes_other_domains(
    httpbin, acurl_session
):
    await acurl_session.get(f"{httpbin.url}/cookies/set?name=value")
    # FIXME: we want to set a cookie for another domain.  There's no easy way
    # to get another domain set up loally, so we (as an exception) go out to
    # the network for this test.
    await acurl_session.get("https://httpbin.org/cookies/set?foo=bar")
    r = await acurl_session.get(f"{httpbin.url}/get")
    assert r.request.cookies == {"name": "value"}
