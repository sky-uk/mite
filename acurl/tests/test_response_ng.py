import pytest
from werkzeug.datastructures import Headers
from werkzeug.wrappers import Response


@pytest.mark.asyncio
async def test_response_headers(httpserver, acurl_session):
    hdrs = Headers()
    hdrs.add("Foo", "bar")
    hdrs.add("Baz", "quux")
    hdrs.add("baz", "quuz")
    httpserver.expect_request("/foo").respond_with_response(
        Response(response="", status=200, headers=hdrs)
    )
    r = await acurl_session.get(httpserver.url_for("/foo"))
    assert "Foo" in r.headers
    assert r.headers["Foo"] == "bar"
    assert r.headers["foo"] == "bar"
    assert "Baz" in r.headers
    assert r.headers["Baz"] == "quux, quuz"
    assert r.headers["baz"] == "quux, quuz"


async def connected_cb(body, reader, writer):
    writer.write(body)
    await writer.drain()
    writer.close()
    await writer.wait_closed()
    await reader.read(-1)


@pytest.mark.asyncio
async def test_response_headers_with_HTTP_100(httpserver, acurl_session):
    hdrs = Headers()
    hdrs.add("Foo", "bar")
    httpserver.expect_request("/foo").respond_with_response(
        Response(response="", status=200, headers=hdrs)
    )
    r = await acurl_session.get(
        httpserver.url_for("/foo"), headers={"Expect": "100-continue"}
    )

    assert "Foo" in r.headers
    assert r.headers["Foo"] == "bar"


@pytest.mark.asyncio
async def test_response_cookies(httpserver, acurl_session):
    hdrs = Headers()
    hdrs.add("Set-Cookie", "foo=bar")
    hdrs.add("Set-Cookie", "quux=xyzzy")
    httpserver.expect_request("/foo").respond_with_response(
        Response(response="", status=200, headers=hdrs)
    )
    r = await acurl_session.get(httpserver.url_for("/foo"))
    assert r.cookies == {"foo": "bar", "quux": "xyzzy"}
