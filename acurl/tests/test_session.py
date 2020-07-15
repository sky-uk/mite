import acurl
import pytest
from werkzeug.wrappers import Response as WZResponse


@pytest.mark.asyncio
async def test_request_no_data_raises():
    loop = acurl.EventLoop()
    s = loop.session()
    with pytest.raises(ValueError):
        await s.request("GET", "http://foo.com", json={}, data="")


@pytest.mark.skip
async def test_invalid_method_raises():
    loop = acurl.EventLoop()
    s = loop.session()
    with pytest.raises(ValueError):
        await s.request("FOO", "http://foo.com")


@pytest.mark.asyncio
async def test_get(httpserver):
    httpserver.expect_oneshot_request("/test", "GET").respond_with_data("hi")
    loop = acurl.EventLoop()
    s = loop.session()
    r = await s.get(httpserver.url_for("/test"))

    assert isinstance(r, acurl.Response)
    assert r.request.method == "GET"
    assert r.body == b"hi"
    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_headers(httpserver):
    httpserver.expect_oneshot_request(
        "/test", "GET", headers={"My-Header": "is-awesome"}
    ).respond_with_data("hi")
    loop = acurl.EventLoop()
    s = loop.session()
    r = await s.get(httpserver.url_for("/test"), headers={"My-Header": "is-awesome"})

    assert isinstance(r, acurl.Response)
    assert r.request.method == "GET"
    assert r.body == b"hi"
    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_post_json(httpserver):
    httpserver.expect_oneshot_request(
        "/test", "POST", data='{"foo":"bar"}'
    ).respond_with_data("hi")
    loop = acurl.EventLoop()
    s = loop.session()

    r = await s.post(httpserver.url_for("/test"), json={"foo": "bar"})

    assert isinstance(r, acurl.Response)
    assert r.request.method == "POST"
    assert r.body == b"hi"
    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_post_data(httpserver):
    httpserver.expect_oneshot_request("/test", "POST", data="foobar").respond_with_data(
        "hi"
    )
    loop = acurl.EventLoop()
    s = loop.session()

    r = await s.post(httpserver.url_for("/test"), data="foobar")

    assert isinstance(r, acurl.Response)
    assert r.request.method == "POST"
    assert r.body == b"hi"
    httpserver.check_assertions()


@pytest.mark.skip
def test_cookies():
    # We'd like to write tests for the cookie functionality, but httpserver
    # doesn't make this easy, so I'm lazily going to skip that for now
    pass


@pytest.mark.asyncio
async def test_response_callback(httpserver):
    httpserver.expect_oneshot_request("/test", "GET").respond_with_data("hi")
    loop = acurl.EventLoop()
    s = loop.session()
    called = False

    def response_cb(resp):
        nonlocal called
        if called:
            raise Exception("called too many times")
        assert isinstance(resp, acurl.Response)
        called = True

    s.set_response_callback(response_cb)
    await s.get(httpserver.url_for("/test"))
    assert called
    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_redirect(httpserver):
    httpserver.expect_oneshot_request("/test", "GET").respond_with_response(
        WZResponse(status=301, headers={"Location": "/test2"})
    )
    httpserver.expect_oneshot_request("/test2", "GET").respond_with_data("hi")

    loop = acurl.EventLoop()
    s = loop.session()
    r = await s.get(httpserver.url_for("/test"))

    assert r.body == b"hi"
    assert r.url == httpserver.url_for("/test2")
    assert r._prev.url == httpserver.url_for("/test")
    assert len(r.history) == 1


@pytest.mark.asyncio
async def test_max_redirects_raises(httpserver):
    httpserver.expect_oneshot_request("/test", "GET").respond_with_response(
        WZResponse(status=301, headers={"Location": "/test2"})
    )

    loop = acurl.EventLoop()
    s = loop.session()
    with pytest.raises(acurl.RequestError):
        await s.get(httpserver.url_for("/test"), max_redirects=0)


@pytest.mark.asyncio
async def test_disallow_redirects(httpserver):
    httpserver.expect_oneshot_request("/test", "GET").respond_with_response(
        WZResponse(status=301, headers={"Location": "/test2"})
    )

    loop = acurl.EventLoop()
    s = loop.session()
    r = await s.get(httpserver.url_for("/test"), allow_redirects=False)

    assert r.status_code == 301
    assert r.headers["Location"].endswith("/test2")
