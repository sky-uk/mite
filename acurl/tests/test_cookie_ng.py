import time

import pytest

import acurl
from acurl import Cookie


@pytest.mark.skip
def test_cookie_zero_expiry():
    # FIXME: what's the right behavior here?
    c = acurl._Cookie(False, "foo.com", False, "/bar", False, 0, "my_cookie", "my_value")
    assert not c.has_expired


def test_cookie_not_expired():
    c = acurl._Cookie(
        False,
        "foo.com",
        False,
        "/bar",
        False,
        time.time() + 200,
        "my_cookie",
        "my_value",
    )
    assert not c.has_expired


def test_cookie_has_expired():
    c = acurl._Cookie(False, "foo.com", False, "/bar", False, 1, "my_cookie", "my_value")
    assert c.has_expired


def test_cookie_format():
    c = acurl._Cookie(False, "foo.com", False, "/bar", False, 0, "my_cookie", "my_value")
    assert c.format() == b"foo.com\tFALSE\t/bar\tFALSE\t0\tmy_cookie\tmy_value"


def test_parse_cookie_string():
    c = acurl.parse_cookie_string("foo.com\tFALSE\t/bar\tFALSE\t0\tmy_cookie\tmy_value")
    assert not c.http_only
    assert c.domain == "foo.com"
    assert not c.include_subdomains
    assert c.path == "/bar"
    assert not c.is_secure
    assert c.expiration == 0
    assert c.name == "my_cookie"
    assert c.value == "my_value"


def test_parse_cookie_string_with_true():
    c = acurl.parse_cookie_string("foo.com\tTRUE\t/bar\tTRUE\t0\tmy_cookie\tmy_value")
    assert not c.http_only
    assert c.domain == "foo.com"
    assert c.include_subdomains
    assert c.path == "/bar"
    assert c.is_secure
    assert c.expiration == 0
    assert c.name == "my_cookie"
    assert c.value == "my_value"


def test_parse_cookie_string_http_only():
    c = acurl.parse_cookie_string(
        "#HttpOnly_foo.com\tFALSE\t/bar\tFALSE\t0\tmy_cookie\tmy_value"
    )
    assert c.http_only
    assert c.domain == "foo.com"
    assert not c.include_subdomains
    assert c.path == "/bar"
    assert not c.is_secure
    assert c.expiration == 0
    assert c.name == "my_cookie"
    assert c.value == "my_value"


def test_session_cookie_for_url_with_cookie_instance():
    c = Cookie("sky.com", "foo", "bar")
    cookie = acurl.session_cookie_for_url(
        url="https://anotherdomain.com", name="baz", value=c
    )
    assert cookie.domain == "sky.com"
    assert cookie.name == "foo"
    assert cookie.value == "bar"


def test_session_cookie_for_url_with_string_value():
    cookie = acurl.session_cookie_for_url(url="https://sky.com", name="foo", value="bar")
    assert cookie.domain == ".sky.com"
    assert cookie.name == "foo"
    assert cookie.value == "bar"
