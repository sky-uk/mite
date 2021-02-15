import pytest
from werkzeug.datastructures import Headers
from werkzeug.wrappers import BaseResponse as Response

import acurl


class MockRawResponse:
    def __init__(self, header):
        self._header = header

    def get_header(self):
        return self._header


def test_response_headers():
    r = acurl.Response(
        "Some Request",
        MockRawResponse(
            [
                b"HTTP/1.1 200 OK\r\n",
                b"Foo: bar\r\n",
                b"Baz: quux\r\n",
                b"baz: quuz\r\n",
                b"\r\n",
            ]
        ),
        0,
    )
    assert "Foo" in r.headers
    assert r.headers["Foo"] == "bar"
    assert r.headers["foo"] == "bar"
    assert "Baz" in r.headers
    assert r.headers["Baz"] == "quux, quuz"
    assert r.headers["baz"] == "quux, quuz"


def test_response_headers_with_HTTP_100():
    r = acurl.Response(
        "Some Request",
        MockRawResponse(
            [
                b"HTTP/1.1 100 Continue\r\n",
                b"\r\n",
                b"HTTP/1.1 200 OK\r\n",
                b"Foo: bar\r\n",
                b"\r\n",
            ]
        ),
        0,
    )
    assert "Foo" in r.headers
    assert r.headers["Foo"] == "bar"


@pytest.mark.asyncio
async def test_response_cookies(httpserver):
    hdrs = Headers()
    hdrs.add("Set-Cookie", "foo=bar")
    hdrs.add("Set-Cookie", "quux=xyzzy")
    httpserver.expect_request("/foo").respond_with_response(
        Response(response="", status=200, headers=hdrs)
    )
    el = acurl.EventLoop()
    el._run_in_thread()
    s = el.session()
    r = await s.get(httpserver.url_for("/foo"))
    assert r.cookies == {"foo": "bar", "quux": "xyzzy"}
