import acurl


def test_request_headers():
    r = acurl.Request(
        "GET", "http://foo.com", ["Foo: bar", "Baz: quux"], [], None, None, None
    )
    assert "Foo" in r.headers
    assert r.headers["Foo"] == "bar"
    assert "Baz" in r.headers
    assert r.headers["Baz"] == "quux"


def test_request_cookies():
    r = acurl.Request(
        "GET",
        "http://foo.com",
        [],
        [
            acurl.parse_cookie_string(
                "foo.com\tFALSE\t/bar\tFALSE\t0\tmy_cookie\tmy_value"
            ),
            acurl.parse_cookie_string("foo.com\tFALSE\t/bar\tFALSE\t0\tfoo\tbar"),
        ],
        None,
        None,
        None,
    )
    assert "my_cookie" in r.cookies
    assert r.cookies["my_cookie"] == "my_value"
    assert "foo" in r.cookies
    assert r.cookies["foo"] == "bar"
