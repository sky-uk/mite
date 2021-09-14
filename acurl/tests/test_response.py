import asyncio
from functools import partial

import pytest
from werkzeug.datastructures import Headers
from werkzeug.wrappers import Response

import acurl


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
async def test_response_headers_with_HTTP_100(acurl_session):
    body = b"".join(
        (
            b"HTTP/1.1 100 Continue\r\n",
            b"\r\n",
            b"HTTP/1.1 200 OK\r\n",
            b"Foo: bar\r\n",
            b"\r\n",
            b"body",
        )
    )
    server = await asyncio.start_server(
        partial(connected_cb, body), host="localhost", port=10763
    )
    await server.start_serving()

    async def go():
        r = await acurl_session.get("http://localhost:10763/foo")
        server.close()
        return r

    results = await asyncio.gather(go(), server.serve_forever(), return_exceptions=True)
    resp = [x for x in results if isinstance(x, acurl._Response)][0]
    assert "Foo" in resp.headers
    assert resp.headers["Foo"] == "bar"


@pytest.mark.asyncio
async def test_response_headers_with_multiple_HTTP_100(acurl_session):
    # It's unclear if this can happen. It doesn't sound like it should, but
    # there's documentation of it happening in IIS at least:
    # https://stackoverflow.com/questions/22818059/several-100-continue-received-from-the-server
    body = b"".join(
        (
            b"HTTP/1.1 100 Continue\r\n",
            b"\r\n",
            b"HTTP/1.1 100 Continue\r\n",
            b"\r\n",
            b"HTTP/1.1 200 OK\r\n",
            b"Foo: bar\r\n",
            b"\r\n",
        )
    )
    server = await asyncio.start_server(
        partial(connected_cb, body), host="localhost", port=10763
    )
    await server.start_serving()

    async def go():
        r = await acurl_session.get("http://localhost:10763/foo")
        server.close()
        return r

    results = await asyncio.gather(go(), server.serve_forever(), return_exceptions=True)
    resp = [x for x in results if isinstance(x, acurl._Response)][0]
    assert "Foo" in resp.headers
    assert resp.headers["Foo"] == "bar"


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
