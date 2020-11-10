import pytest

import acurl
from acurl import Request


def test_to_curl():
    r = Request("GET", "http://foo.com", (), (), None, None, None)
    assert r.to_curl() == "curl -X GET     http://foo.com"


def test_to_curl_headers():
    r = Request(
        "GET",
        "http://foo.com",
        ("Foo: bar", "My-Header: is-awesome"),
        (),
        None,
        None,
        None,
    )
    assert (
        r.to_curl()
        == "curl -X GET -H 'Foo: bar' -H 'My-Header: is-awesome'    http://foo.com"
    )


def test_to_curl_cookies():
    r = Request(
        "GET",
        "http://foo.com",
        (),
        (acurl.Cookie(False, "foo.com", True, "/", False, 0, "123", "456"),),
        None,
        None,
        None,
    )
    assert r.to_curl() == "curl -X GET  --cookie 123=456   http://foo.com"


def test_to_curl_multiple_cookies():
    r = Request(
        "GET",
        "http://foo.com",
        (),
        (
            acurl.Cookie(False, "foo.com", True, "/", False, 0, "123", "456"),
            acurl.Cookie(False, "foo.com", True, "/", False, 0, "789", "abc"),
        ),
        None,
        None,
        None,
    )
    assert r.to_curl() == "curl -X GET  --cookie '123=456;789=abc'   http://foo.com"


@pytest.mark.skip(reason="unimplemented")
def test_to_curl_cookies_wrong_domain():
    # I'm not sure if this is a valid test case...Request objects should
    # probably only be constructed via Session.request, which always creates
    # cookies for the domain of the request.  So the case this is exercising
    # won't ever happen.
    r = Request(
        "GET",
        "http://foo.com",
        (),
        (
            acurl.Cookie(
                False,
                "bar.com",  # The domain doesn't match, the cookie should not be passed
                True,
                "/",
                False,
                0,
                "123",
                "456",
            ),
        ),
        None,
        None,
        None,
    )
    assert r.to_curl() == "curl -X GET http://foo.com"


def test_to_curl_auth():
    r = Request("GET", "http://foo.com", (), (), ("user", "pass"), None, None)
    assert r.to_curl() == "curl -X GET   --user user:pass  http://foo.com"
