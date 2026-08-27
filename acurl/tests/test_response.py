import asyncio
import pytest
from werkzeug.datastructures import Headers
from werkzeug.wrappers import Response


@pytest.fixture
async def raw_response_server():
    """Serve a canned byte blob, so tests can exercise wire-level responses
    (interim 1xx blocks) that werkzeug's dev server cannot produce."""
    servers = []

    async def serve(payload):
        async def handle(reader, writer):
            await reader.readuntil(b"\r\n\r\n")  # consume the request
            writer.write(payload)
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        servers.append(server)
        host, port = server.sockets[0].getsockname()[:2]
        return f"http://{host}:{port}/"

    yield serve

    for server in servers:
        server.close()
        await server.wait_closed()


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


EARLY_HINTS_RESPONSE = (
    b"HTTP/1.1 103 Early Hints\r\n"
    b"link: </style.css>; rel=preload; as=style\r\n"
    b"\r\n"
    b"HTTP/1.1 200 OK\r\n"
    b"Foo: bar\r\n"
    b"Content-Length: 2\r\n"
    b"\r\n"
    b"hi"
)


@pytest.mark.asyncio
async def test_response_headers_with_HTTP_103(raw_response_server, acurl_session):
    url = await raw_response_server(EARLY_HINTS_RESPONSE)
    r = await acurl_session.get(url)

    assert r.status_code == 200
    assert r.body == b"hi"
    assert r.headers["Foo"] == "bar"
    assert r.headers["Content-Length"] == "2"
    # headers from the interim block must not leak into the final response
    assert "link" not in r.headers


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
