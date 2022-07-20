import pytest
from helpers import create_request

import acurl


def test_to_curl():
    r = create_request("GET", "http://foo.com")
    assert r.to_curl() == "curl -X GET http://foo.com"


def test_to_curl_headers():
    r = create_request(
        "GET", "http://foo.com", headers=("Foo: bar", "My-Header: is-awesome")
    )
    assert (
        r.to_curl()
        == "curl -X GET -H 'Foo: bar' -H 'My-Header: is-awesome' http://foo.com"
    )


def test_to_curl_cookies():
    r = create_request(
        "GET",
        "http://foo.com",
        cookies=(
            acurl._Cookie(False, "foo.com", True, "/", False, 0, "123", "456").format(),
        ),
    )
    assert r.to_curl() == "curl -X GET --cookie 123=456 http://foo.com"


def test_to_curl_multiple_cookies():
    r = create_request(
        "GET",
        "http://foo.com",
        cookies=(
            acurl._Cookie(False, "foo.com", True, "/", False, 0, "123", "456").format(),
            acurl._Cookie(False, "foo.com", True, "/", False, 0, "789", "abc").format(),
        ),
    )
    assert r.to_curl() == "curl -X GET --cookie '123=456;789=abc' http://foo.com"


# FIXME: curl won't send cookies that don't match the domain.
# https://curl.se/docs/http-cookies.html
# Should we ignore cookies that won't be sent?
@pytest.mark.skip(reason="unimplemented")
def test_to_curl_cookies_wrong_domain():
    # I'm not sure if this is a valid test case...Request objects should
    # probably only be constructed via Session.request, which always creates
    # cookies for the domain of the request.  So the case this is exercising
    # won't ever happen.
    r = create_request(
        "GET",
        "http://foo.com",
        # The domain doesn't match, the cookie should not be passed
        cookies=(
            acurl._Cookie(False, "bar.com", True, "/", False, 0, "123", "456").format(),
        ),
    )
    assert r.to_curl() == "curl -X GET http://foo.com"


def test_to_curl_auth():
    r = create_request("GET", "http://foo.com", auth=("user", "pass"))
    assert r.to_curl() == "curl -X GET --user user:pass http://foo.com"
