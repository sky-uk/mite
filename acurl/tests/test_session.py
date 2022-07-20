import pytest
from werkzeug.wrappers import Response as WZResponse

import acurl


@pytest.mark.asyncio
async def test_request_no_data_raises(acurl_session):
    with pytest.raises(ValueError):
        await acurl_session.get("http://foo.com", json={}, data="")


@pytest.mark.asyncio
async def test_get(httpserver, acurl_session):
    httpserver.expect_oneshot_request("/test", "GET").respond_with_data("hi")
    r = await acurl_session.get(httpserver.url_for("/test"))

    assert isinstance(r, acurl._Response)
    assert r.request.method == b"GET"
    assert r.body == b"hi"
    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_get_headers(httpserver, acurl_session):
    httpserver.expect_oneshot_request(
        "/test", "GET", headers={"My-Header": "is-awesome"}
    ).respond_with_data("hi")
    r = await acurl_session.get(
        httpserver.url_for("/test"), headers={"My-Header": "is-awesome"}
    )

    assert isinstance(r, acurl._Response)
    assert r.request.method == b"GET"
    assert r.body == b"hi"
    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_post_json(httpserver, acurl_session):
    httpserver.expect_oneshot_request(
        "/test",
        "POST",
        json={"foo": "bar"},
        headers={"content-type": "application/json"},
    ).respond_with_data("hi")

    r = await acurl_session.post(httpserver.url_for("/test"), json={"foo": "bar"})

    assert isinstance(r, acurl._Response)
    assert r.request.method == b"POST"
    assert r.body == b"hi"
    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_post_data(httpserver, acurl_session):
    httpserver.expect_oneshot_request("/test", "POST", data="foobar").respond_with_data(
        "hi"
    )

    r = await acurl_session.post(httpserver.url_for("/test"), data="foobar")

    assert isinstance(r, acurl._Response)
    assert r.request.method == b"POST"  # FIXME: should it be a string?
    assert r.body == b"hi"
    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_response_callback(httpserver, acurl_session):
    httpserver.expect_oneshot_request("/test", "GET").respond_with_data("hi")
    called = False

    def response_cb(resp):
        nonlocal called
        if called:
            raise Exception("called too many times")
        assert isinstance(resp, acurl._Response)
        called = True

    acurl_session.response_callback = response_cb
    await acurl_session.get(httpserver.url_for("/test"))
    assert called
    httpserver.check_assertions()


@pytest.mark.asyncio
async def test_redirect(httpserver, acurl_session):
    httpserver.expect_oneshot_request("/test", "GET").respond_with_response(
        WZResponse(status=301, headers={"Location": "/test2"})
    )
    httpserver.expect_oneshot_request("/test2", "GET").respond_with_data("hi")

    r = await acurl_session.get(httpserver.url_for("/test"))

    assert r.body == b"hi"
    assert r.url == httpserver.url_for("/test2")
    h = r.history
    assert len(h) == 1
    assert h[0].url == httpserver.url_for("/test")


@pytest.mark.asyncio
async def test_max_redirects_raises(httpserver, acurl_session):
    httpserver.expect_oneshot_request("/test", "GET").respond_with_response(
        WZResponse(status=301, headers={"Location": "/test2"})
    )

    with pytest.raises(acurl.RequestError):
        await acurl_session.get(httpserver.url_for("/test"), max_redirects=0)


@pytest.mark.asyncio
async def test_disallow_redirects(httpserver, acurl_session):
    httpserver.expect_oneshot_request("/test", "GET").respond_with_response(
        WZResponse(status=301, headers={"Location": "/test2"})
    )

    r = await acurl_session.get(httpserver.url_for("/test"), allow_redirects=False)

    assert r.status_code == 301
    assert r.headers["Location"].endswith("/test2")
